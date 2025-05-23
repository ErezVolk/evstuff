#!/usr/bin/env python
"""A simple metronome.

Metronome sounds recorded by Ludwig Peter Müller (muellerwig@gmail.com)
and distributed under the Creative Commons CC0 1.0 Universal license.
https://www.reddit.com/r/audioengineering/comments/kg8gth/free_click_track_sound_archive/?rdt=48837
Zip file: https://stash.reaper.fm/40824/Metronomes.zip
"""
# pyright: reportMissingImports=false
# pyright: reportMissingModuleSource=false
# pyright: reportAttributeAccessIssue=false
# pylint: disable=import-error
# pylint: disable=no-name-in-module
# pylint: disable=c-extension-no-member
# mypy: disable-error-code="import-untyped,import-not-found"

import argparse
import bisect
import logging
import re
import signal
import time
import typing as t
import wave
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePath
from types import FrameType

import numpy as np
import pyaudio
import rich
import rich.console
import rich.live
import rich.logging
from soundfile import SoundFile

# CGEventRef is impossible(?) to properly type
CGEventRef = t.NewType("CGEventRef", object)
CGEventRefOpt: t.TypeAlias = CGEventRef | None

try:
    import pynput.keyboard
    from Quartz import CGEventMaskBit
    from Quartz import NSEvent
    from Quartz import NSSystemDefined

    # pylint: disable-next=too-few-public-methods
    class MiniListener(pynput.keyboard.Listener):
        """A Listener that only cares about media keys."""

        _EVENTS = CGEventMaskBit(NSSystemDefined)

    WITH_MEDIA_KEYS = True
except ImportError:
    print("Warning: No media key support (try installing pynput)")
    CGEventMaskBit = NSEvent = NSSystemDefined = None
    WITH_MEDIA_KEYS = False


THIS = Path(__file__).resolve()
HERE = THIS.parent

# Media keys from <hidsystem/ev_keymap.h>
NX_KEYTYPE_EJECT = 14
NX_KEYTYPE_PLAY = 16
NX_KEYTYPE_FAST = 19
NX_KEYTYPE_REWIND = 20
NX_KEYTYPE_ILLUMINATION_UP = 21
NX_KEYTYPE_ILLUMINATION_DOWN = 22

SHIFT_FLAG = 1 << 17  # NSEventModifierFlagShift
KEY_DOWN = 10  # NSEventTypeKeyDown


class ByteLoop:
    """A circular buffer of bytes."""

    def __init__(self, data: bytes | bytearray, granularity: int) -> None:
        self.data = data
        self.offset = 0
        self.granularity = granularity

    def get(self, nbytes: int) -> bytes:
        """Get another chunk."""
        limit = min(self.offset + nbytes, len(self.data))
        chunk = self.data[self.offset:limit]
        self.offset = limit % len(self.data)
        return chunk

    def make_like(self, other: "ByteLoop") -> None:
        """Set offset to the corresponding one."""
        if other.offset:
            ideal = (other.offset / len(other.data)) * len(self.data)
            self.offset = int(ideal / self.granularity) * self.granularity


@dataclass
class SoundShape:
    """Sound file parameters."""

    channels: int
    rate: int
    width: int


# pylint: disable-next=too-few-public-methods
class Click(SoundShape):
    """Audio data of a click."""

    data: bytes

    def __init__(self, path: str | Path) -> None:
        try:
            # Try Python's `wave` first, because `SoundFile` *sets* the width
            with wave.open(str(path), "rb") as wavo:
                super().__init__(
                    channels=wavo.getnchannels(),
                    rate=wavo.getframerate(),
                    width=wavo.getsampwidth(),
                )
                self.data = wavo.readframes(wavo.getnframes())
        except wave.Error:
            with SoundFile(str(path)) as sfo:
                super().__init__(
                    channels=sfo.channels,
                    rate=sfo.samplerate,
                    width=2,
                )
                self.data = bytes(sfo.frames * self.channels * self.width)
                sfo.buffer_read_into(self.data, dtype="int16")

    def is_compatible_with(self, other: SoundShape) -> bool:
        """We only support clicks with the same frame rate, etc."""
        return other == self  # This is why SoundShape is a dataclass


class PathAwareDefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Like ArgumentDefaultsHelpFormatter, but with nicer Path formatting."""

    DEFAULTING_NARGS = (argparse.OPTIONAL, argparse.ZERO_OR_MORE)

    def _get_help_string(self, action: argparse.Action) -> str | None:
        result = action.help
        if result is None:
            return result

        if "%(default)" in result:
            return result

        if (default := action.default) is argparse.SUPPRESS:
            return result

        if default is None:
            return result

        if action.option_strings or action.nargs in self.DEFAULTING_NARGS:
            if isinstance(default, PurePath):
                result += f" [.../{default.name}]"
            elif isinstance(default, list | tuple):
                if all(isinstance(elem, PurePath) for elem in default):
                    names = ", ".join(elem.name for elem in default)
                    result += f" [{names}]"
                else:
                    result += " %(default)s"  # The list has brackets
            else:
                result += " [%(default)s]"

        return result


# pylint: disable-next=too-many-instance-attributes,too-many-public-methods
class Metronome:
    """A simple metronome."""

    args: argparse.Namespace
    status: rich.live.Live
    bytes_per_frame: int
    log: logging.Logger
    loop: ByteLoop = ByteLoop(b"", 0)
    next_loop: ByteLoop | None = None
    aborting: bool = False
    paused: bool = True
    media_keys: dict[int, t.Callable]
    shape: SoundShape
    hi_click: Click
    lo_click: Click
    beats_per_bar: int
    pattern: dict[float, bytes]
    tempo: int
    suffix: str = ""

    bpms: tuple[int, ...] = (
        # Added by me
        20, 22, 24, 26, 28, 30, 32, 34, 36, 38,

        # https://en.wikipedia.org/wiki/Metronome#Usage
        40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60,
        63, 66, 69, 72,
        76, 80, 84, 88, 92, 96, 100, 104, 108, 112, 116, 120,
        126, 132, 138, 144,
        152, 160, 168, 176, 184, 192, 200, 208,

        # Added by me
        216, 224, 232, 240,
    )

    def parse_args(self) -> None:
        """Parse command line."""
        parser = argparse.ArgumentParser(
            description="A metronome",
            formatter_class=PathAwareDefaultsHelpFormatter,
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "tempo",
            metavar="BPM",
            type=int,
            nargs="?",
            default=92,
            help="beats per minute",
        )
        group.add_argument(
            "-T",
            "--ask-tempo",
            action="store_true",
            help="ask for tempo",
        )
        parser.add_argument(
            "-c",
            "--click",
            type=Path,
            metavar="AUDIO_FILE",
            nargs="+",
            default=[
                HERE / "Perc_MetronomeQuartz_hi.wav",
                HERE / "Perc_MetronomeQuartz_lo.wav",
            ],
            help="click sound (one or two)",
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-b",
            "--beats",
            type=int,
            nargs="+",
            default=[4],
            help=(
                "number of beats per bar. "
                "use multiple values for compound rhythms"
            ),
        )
        group.add_argument(
            "-r",
            "--rhythm",
            choices=[
                "half",
                "quarter",
                "eighth",
                "triple",
                "clave",
            ],
            help="common rhythms",
        )
        group.add_argument(
            "-s",
            "--subdivision",
            type=self.validate_subdivision_arg,
            help=(
                "roll your own sub-beat rhythms with a combination of "
                "'T' = high click, 't' = low click, and '-' = rest. "
                "E.g., 't-t' is a first- and third triplet "
                "beat, and '-t' clicks on the second eighth."
            ),
        )
        parser.add_argument(
            "-p",
            "--start-paused",
            action="store_true",
            help="Start paused.",
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="print debugging info",
        )
        self.args = parser.parse_args()
        if self.args.beats != [0]:
            if not all(beats > 0 for beats in self.args.beats):
                parser.error("--beats must be all positive or a single zero")

    @classmethod
    def validate_subdivision_arg(cls, arg: str) -> str:
        """Validate --subdivision argument."""
        if re.fullmatch(r"[-tT]*[tT][-tT]*", arg):
            return arg
        raise argparse.ArgumentTypeError("may only contain 'T', 't', and '-'")

    def run(self) -> None:
        """Be a metronome."""
        self.parse_args()
        self.configure_logging()
        self.figure_tempo()

        with rich.live.Live("Loading...") as self.status:
            self.do_run()

    def do_run(self) -> None:
        """Run, with `self.status` initialized."""
        self.read_clicks()
        self.figure_pattern()

        self.make_loop()
        self.listen_to_control_c()
        self.listen_to_media_keys()

        self.main_loop()

    def configure_logging(self) -> None:
        """Set logging format and level."""
        level = logging.DEBUG if self.args.debug else logging.INFO
        logging.basicConfig(
            format="%(message)s",
            datefmt="[%X]",
            level=level,
            handlers=[rich.logging.RichHandler()],
        )
        self.log = logging.getLogger(Path(__file__).stem)

    def listen_to_control_c(self) -> None:
        """Install signal handler, otherwise pyaudio loses it."""
        signal.signal(signal.SIGINT, self.handle_ctrl_c)

    def listen_to_media_keys(self) -> None:
        """On MacOS, start event intercept thread for play/pause, etc."""
        if WITH_MEDIA_KEYS:
            self.media_keys = {
                NX_KEYTYPE_EJECT: self.handle_eject,
                NX_KEYTYPE_PLAY: self.handle_play_pause,
                NX_KEYTYPE_FAST: self.handle_fast_forward,
                NX_KEYTYPE_REWIND: self.handle_rewind,
                NX_KEYTYPE_ILLUMINATION_UP: self.handle_illumination_up,
            }
            listener = MiniListener(darwin_intercept=self.intercept)
            listener.start()

    def main_loop(self) -> None:
        """Keep playing until pause or abort."""
        player = pyaudio.PyAudio()
        self.pause_unpause(paused=self.args.start_paused)  # Get ready to play

        while not self.aborting:
            # Every pass through the loop is playing, then pause/abort
            stream = player.open(
                format=player.get_format_from_width(self.shape.width),
                channels=self.shape.channels,
                rate=self.shape.rate,
                output=True,
                stream_callback=self.read_more,
            )

            while stream.is_active():
                time.sleep(0.1)

            stream.close()

            while self.paused and not self.aborting:
                time.sleep(0.1)

        player.terminate()

    def read_clicks(self) -> None:
        """Read click sounds."""
        paths = self.args.click
        self.lo_click = self.hi_click = Click(paths[0])
        if len(paths) > 1:
            self.lo_click = Click(paths[1])
            if not self.lo_click.is_compatible_with(self.hi_click):
                self.lo_click = self.hi_click
                rich.print(
                    f"{paths[0]} and {paths[1]} are incompatible, "
                    f"using only {paths[0]}.",
                )
        self.shape = self.hi_click
        self.bytes_per_frame = self.shape.channels * self.shape.width

    def figure_pattern(self) -> None:
        """Figure out where in the bar we need which clicks."""
        his: list[float] = []
        los: list[float] = []
        if self.args.subdivision:
            self.beats_per_bar = 1
            mnems = np.array(list(self.args.subdivision))
            los = (np.flatnonzero(mnems == "t") / len(mnems)).tolist()
            his = (np.flatnonzero(mnems == "T") / len(mnems)).tolist()
        elif self.args.rhythm == "half":
            self.beats_per_bar = 4
            (los if self.args.beats == [0] else his).extend([0, 2])
        elif self.args.rhythm == "quarter":
            self.beats_per_bar = 1
            his = [0]
        elif self.args.rhythm == "eighth":
            self.beats_per_bar = 1
            his = [0]
            los = [0.5]
        elif self.args.rhythm == "triple":
            self.beats_per_bar = 1
            his = [0]
            los = [1 / 3, 2 / 3]
        elif self.args.rhythm == "clave":
            self.beats_per_bar = 4
            his = [0, 0.75, 1.5, 2.5, 3]
        elif self.args.beats == [0]:
            self.beats_per_bar = 1
            los = [0]
        else:
            self.beats_per_bar = 0
            for beats in self.args.beats:
                his.append(self.beats_per_bar)
                self.beats_per_bar += beats
            los = list(range(self.beats_per_bar))  # Will get overrun by his

        self.pattern = {lo: self.lo_click.data for lo in los}
        self.pattern.update({hi: self.hi_click.data for hi in his})

    def read_more(
        self,
        in_data: bytes | None,
        frame_count: int,
        time_info: t.Mapping[str, float],
        status: int,
    ) -> tuple[bytes, int]:
        """Supply pyaudio with more audio."""
        del in_data, time_info, status  # unused

        if self.aborting or self.paused:
            return (b"", pyaudio.paAbort)

        nbytes = frame_count * self.bytes_per_frame
        chunks = []

        while nbytes > 0 and not self.paused:
            if self.next_loop is not None:
                next_loop = self.next_loop
                self.next_loop = None
                next_loop.make_like(self.loop)
                self.loop = next_loop

            chunk = self.loop.get(nbytes)
            chunks.append(chunk)
            nbytes -= len(chunk)

        data = b"".join(chunks)
        return (data, pyaudio.paContinue)

    def figure_tempo(self) -> None:
        """Set initial tempo."""
        if self.args.ask_tempo:
            console = rich.console.Console()
            self.tempo = int(console.input("Please enter tempo in BPM: "))
        else:
            self.tempo = self.args.tempo
        if self.tempo not in self.bpms:
            self.bpms = tuple(sorted([self.tempo, *self.bpms]))

    def set_tempo(self, tempo: int) -> None:
        """Set (with limits) a new tempo."""
        self.tempo = min(self.bpms[-1], max(self.bpms[0], tempo))
        self.make_loop()

    def make_loop(self) -> None:
        """Rebuild the audio loop."""
        frames_per_beat = (60 / self.tempo) * self.shape.rate
        frames_per_bar = round(self.beats_per_bar * frames_per_beat)
        bars_per_loop = 1
        loop_size = frames_per_bar * self.bytes_per_frame

        loop_data = bytearray(loop_size)
        for n_bar in range(bars_per_loop):
            for pos, data in self.pattern.items():
                beat_n = (n_bar * self.beats_per_bar) + pos
                frame_n = beat_n * frames_per_beat
                offset = round(frame_n) * self.bytes_per_frame
                limit = offset + len(data)
                loop_data[offset:limit] = data

        loop = ByteLoop(loop_data, self.bytes_per_frame)
        self.next_loop = loop
        self.show_tempo()

    def handle_ctrl_c(self, sig: int, frame: FrameType | None) -> None:
        """Handle Ctrl-C."""
        del sig, frame  # unused
        self.abort()

    def abort(self) -> None:
        """Tell the player to stop."""
        self.status.update("Aborting...")
        self.aborting = True

    def intercept(self, event_type: int, event: CGEventRef) -> CGEventRefOpt:
        """Handle MacOS media key event."""
        assert NSEvent is not None, "Who called this function?!"
        del event_type  # unused
        details = NSEvent.eventWithCGEvent_(event)
        flags = details.modifierFlags()
        shift = bool(flags & SHIFT_FLAG)
        bitmap = details.data1()
        key = (bitmap & 0xFFFF0000) >> 16

        handler = self.media_keys.get(key)
        if handler is None:
            self.log.debug("bitmap=%X key=%d flags=%X", bitmap, key, flags)
            return event

        is_press = ((bitmap & 0xFF00) >> 8) == KEY_DOWN
        if not is_press:  # React on key release
            handler(shift=shift)
        return None

    def handle_eject(self, **_: bool) -> None:
        """Handle ⏏."""
        self.abort()

    def handle_play_pause(self, **_: bool) -> None:
        """Handle ⏯."""
        self.pause_unpause()

    def pause_unpause(self, paused: bool | None = None) -> None:
        """Toggle play/pause status."""
        if paused is None:
            self.paused = not self.paused
        else:
            self.paused = paused
        self.show_tempo()

    def show_tempo(self) -> None:
        """Update status to show the current tempo."""
        suffix = self.suffix
        if self.paused:
            suffix += " ⏾"
        self.status.update(f"Tempo: ♩ = {self.tempo}{suffix}")

    def handle_fast_forward(self, *, shift: bool) -> None:
        """Handle ⏩."""
        self.change_tempo(direction=1, fine=shift)

    def handle_rewind(self, *, shift: bool) -> None:
        """Handle ⏪."""
        self.change_tempo(direction=-1, fine=shift)

    def handle_illumination_up(self, **_: bool) -> None:
        """(F6) Toggle half time."""
        if self.args.beats not in ([0], [4]):
            return

        paused = self.paused
        self.paused = True
        if not self.args.rhythm:
            self.log.debug("Switching to 2/2")
            self.args.rhythm = "half"
            self.suffix = " (half)"
        else:
            self.log.debug("Switching to 4/4")
            self.args.rhythm = None
            self.suffix = ""
        self.figure_pattern()
        self.make_loop()

        self.paused = paused
        self.show_tempo()

    def change_tempo(self, *, direction: int, fine: bool = False) -> None:
        """Increase/decrease tempo."""
        if fine:
            self.set_tempo(self.tempo + direction)
            return

        if direction > 0:  # Increase tempo
            idx = bisect.bisect_right(self.bpms, self.tempo)
        else:
            idx = bisect.bisect_left(self.bpms, self.tempo) - 1
        if 0 <= idx < len(self.bpms):
            self.set_tempo(self.bpms[idx])


if __name__ == "__main__":
    Metronome().run()
