#!/usr/bin/env python3
"""A simple metronome"""
import argparse
from pathlib import Path
import re
import signal
import time
import typing as t
import wave

from soundfile import SoundFile
import pyaudio
import rich.live
from rich import print  # pylint: disable=redefined-builtin

try:
    import pynput.keyboard
    from Quartz import CGEventMaskBit, NSEvent, NSSystemDefined  # type: ignore

    # pylint: disable-next=too-few-public-methods
    class MiniListener(pynput.keyboard.Listener):
        """A Listener that only cares about media keys"""
        _EVENTS = CGEventMaskBit(NSSystemDefined)

    WITH_MEDIA_KEYS = True
except ImportError:
    print("Warning: No media key support")
    WITH_MEDIA_KEYS = False

# TODO: save/use named configs


# Metronome sounds recorded by Ludwig Peter Müller (muellerwig@gmail.com)
# and distributed under the Creative Commons CC0 1.0 Universal license.
# https://www.reddit.com/r/audioengineering/comments/kg8gth/free_click_track_sound_archive/?rdt=48837
# Zip file: https://stash.reaper.fm/40824/Metronomes.zip

THIS = Path(__file__).resolve()
HERE = THIS.parent

# Media keys from <hidsystem/ev_keymap.h>
NX_KEYTYPE_EJECT = 14
NX_KEYTYPE_PLAY = 16
NX_KEYTYPE_FAST = 19
NX_KEYTYPE_REWIND = 20


class ByteLoop:
    """A circular buffer of bytes."""
    def __init__(self, data: bytes | bytearray, granularity: int):
        self.data = data
        self.offset = 0
        self.granularity = granularity

    def get(self, nbytes: int) -> bytes:
        """Get another chunk"""
        limit = min(self.offset + nbytes, len(self.data))
        chunk = self.data[self.offset:limit]
        self.offset = limit % len(self.data)
        return chunk

    def make_like(self, other: "ByteLoop"):
        """Set offset to the corresponding one"""
        if other.offset:
            ideal = (other.offset / len(other.data)) * len(self.data)
            self.offset = int(ideal / self.granularity) * self.granularity


# pylint: disable-next=too-few-public-methods
class Click:
    """Helper for reading sound files"""
    channels: int
    rate: int
    width: int
    data: bytes

    def __init__(self, path: str | Path):
        try:
            with wave.open(str(path), "rb") as wavo:
                self.channels = wavo.getnchannels()
                self.rate = wavo.getframerate()
                self.width = wavo.getsampwidth()
                self.data = wavo.readframes(wavo.getnframes())
        except wave.Error:
            with SoundFile(str(path)) as sfo:
                self.channels = sfo.channels
                self.rate = sfo.samplerate
                self.width = 2
                self.data = bytes(sfo.frames * self.channels * self.width)
                sfo.buffer_read_into(self.data, dtype='int16')

    def is_like(self, other: "Click") -> bool:
        """Are two clicks compatible"""
        if self.channels != other.channels:
            return False
        if self.rate != other.rate:
            return False
        if self.width != other.width:
            return False
        return True


# pylint: disable-next=too-many-instance-attributes
class Metronome:
    """A simple metronome"""
    args: argparse.Namespace
    status: rich.live.Live
    bytes_per_frame: int
    loop: ByteLoop = ByteLoop(b'', 0)
    next_loop: ByteLoop | None = None
    aborting: bool = False
    paused: bool = True
    media_keys: dict[int, t.Callable]
    channels: int
    rate: int
    width: int
    hi_click: Click
    lo_click: Click
    beats_per_bar: int
    pattern: dict[float, bytes] = {}
    tempo: int

    MIN_BPM = 20
    MAX_BPM = 240
    BPM_STEP = 5

    def parse_args(self):
        """Usage"""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "tempo",
            metavar="BPM",
            type=int,
            nargs="?",
            default=90,
            help="beats per minute",
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
            type=self.validate_beat_arg,
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
            choices=["quarter", "eighth", "triple", "clave"],
            help="common rhythms",
        )
        group.add_argument(
            "-s",
            "--subdivision",
            type=self.validate_subdivision_arg,
            help=(
                "roll your own sub-beat rhythms with a string. "
                "'T' = high click; 't' = low click; '-' = rest. "
                "E.g., 't-t' is a first- and third triplet "
                "beat, and '-t' clicks on the second eighth. "
            )
        )
        self.args = parser.parse_args()

    @classmethod
    def validate_subdivision_arg(cls, arg: str) -> str:
        """Validate --subdivision argument"""
        if re.fullmatch(r"[-tT]*[tT][-tT]*", arg):
            return arg
        raise argparse.ArgumentTypeError("may only contain 'T', 't', and '-'")

    @classmethod
    def validate_beat_arg(cls, arg: str) -> int:
        """Validate --beat argument"""
        if not str.isnumeric(arg):
            raise argparse.ArgumentTypeError("must be a number")
        beat = int(arg)
        if beat <= 0:
            raise argparse.ArgumentTypeError("must be positive")
        return beat

    def run(self):
        """The main event"""
        self.parse_args()

        with rich.live.Live("Loading...") as self.status:
            self.do_run()

    def do_run(self):
        """The main event, with `self.status` initialized"""
        self.read_clicks()
        self.figure_pattern()

        self.set_tempo(self.args.tempo)

        # Listen to Ctrl-C
        signal.signal(signal.SIGINT, self.handle_ctrl_c)

        # Listen to Media keys
        if WITH_MEDIA_KEYS:
            self.media_keys = {
                NX_KEYTYPE_EJECT: self.handle_eject,
                NX_KEYTYPE_PLAY: self.handle_play_pause,
                NX_KEYTYPE_FAST: self.handle_fast_forward,
                NX_KEYTYPE_REWIND: self.handle_rewind,
            }
            listener = MiniListener(darwin_intercept=self.intercept)
            listener.start()

        player = pyaudio.PyAudio()
        self.pause_unpause()  # Get ready for playing

        while not self.aborting:
            # Every pass through the loop is playing, then pause/abort
            stream = player.open(
                format=player.get_format_from_width(self.width),
                channels=self.channels,
                rate=self.rate,
                output=True,
                stream_callback=self.read_more,
            )

            while stream.is_active():
                time.sleep(.1)

            stream.close()

            while self.paused and not self.aborting:
                time.sleep(.1)

        player.terminate()

    def read_clicks(self):
        """Read click sounds"""
        paths = self.args.click
        self.lo_click = self.hi_click = Click(paths[0])
        if len(paths) > 1:
            self.lo_click = Click(paths[1])
            if not self.lo_click.is_like(self.hi_click):
                self.lo_click = self.hi_click
                print(
                    f"{paths[0]} and {paths[1]} are incompatible, "
                    f"using only {paths[0]}."
                )
        self.channels = self.hi_click.channels
        self.rate = self.hi_click.rate
        self.width = self.hi_click.width
        self.bytes_per_frame = self.channels * self.width

    def figure_pattern(self):
        """Figure out where in the bar we need which clicks"""
        los = []
        if self.args.subdivision:
            self.beats_per_bar = 1
            subs = len(self.args.subdivision)
            his = []
            for where, mnem in enumerate(self.args.subdivision):
                if mnem == "T":
                    his.append(where / subs)
                elif mnem == "t":
                    los.append(where / subs)
        elif self.args.rhythm == "quarter":
            self.beats_per_bar = 1
            his = [0]
        elif self.args.rhythm == "eighth":
            self.beats_per_bar = 1
            his = [0]
            los = [.5]
        elif self.args.rhythm == "triple":
            self.beats_per_bar = 1
            his = [0]
            los = [1 / 3, 2 / 3]
        elif self.args.rhythm == "clave":
            self.beats_per_bar = 4
            his = [0, .75, 1.5, 2.5, 3]
        else:
            his = []
            self.beats_per_bar = 0
            for beats in self.args.beats:
                his.append(self.beats_per_bar)
                self.beats_per_bar += beats
            los = range(self.beats_per_bar)  # Will get overrun by his

        for click, where in ((self.lo_click, los), (self.hi_click, his)):
            for pos in where:
                self.pattern[pos] = click.data

    # pylint: disable-next=unused-argument
    def read_more(self, in_data, frame_count, time_info, status):
        """Supply pyaudio with more audio"""
        if self.aborting or self.paused:
            return (b'', pyaudio.paAbort)

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

        data = b''.join(chunks)
        return (data, pyaudio.paContinue)

    def set_tempo(self, tempo):
        """Set (with limits) a new tempo"""
        self.tempo = min(self.MAX_BPM, max(self.MIN_BPM, tempo))
        self.make_loop()

    def make_loop(self):
        """Rebuild the audio loop"""
        beat_sec = 60 / self.tempo
        ideal_bar_frames = self.beats_per_bar * beat_sec * self.rate
        ideal_bar = ideal_bar_frames * self.bytes_per_frame
        bars_per_loop = 1
        rounded_frames = round(ideal_bar / self.bytes_per_frame)
        loop_size = rounded_frames * self.bytes_per_frame

        loop_data = bytearray(loop_size)
        for n_bar in range(bars_per_loop):
            for pos, data in self.pattern.items():
                beat_n = (n_bar * self.beats_per_bar) + pos
                frame_n = beat_n * beat_sec * self.rate
                offset = round(frame_n) * self.bytes_per_frame
                loop_data[offset:offset + len(data)] = data

        loop = ByteLoop(loop_data, self.bytes_per_frame)
        self.next_loop = loop
        self.show_tempo()

    # pylint: disable-next=unused-argument
    def handle_ctrl_c(self, sig, frame):
        """Handle Ctrl-C"""
        self.abort()

    def abort(self):
        """Tell the player to stop"""
        self.status.update("Aborting...")
        self.aborting = True

    # pylint: disable-next=unused-argument
    def intercept(self, event_type, event):
        """Handle MacOS media key event"""
        bitmap = NSEvent.eventWithCGEvent_(event).data1()
        key = (bitmap & 0xffff0000) >> 16

        handler = self.media_keys.get(key)
        if handler is None:
            return event

        is_press = ((bitmap & 0xff00) >> 8) == 0x0a
        if not is_press:  # React on key release
            handler()
        return None

    def handle_eject(self):
        """On ⏏"""
        self.abort()

    def handle_play_pause(self):
        """On ⏯"""
        self.pause_unpause()

    def pause_unpause(self):
        """Toggle play/pause status"""
        self.paused = not self.paused
        self.show_tempo()

    def show_tempo(self):
        """Update status to show the current tempo"""
        if self.paused:
            suffix = " ⏾"
        else:
            suffix = ""
        self.status.update(f"Tempo: ♩ = {self.tempo}{suffix}")

    def handle_fast_forward(self):
        """On ⏩"""
        self.change_tempo(1)

    def handle_rewind(self):
        """On ⏪"""
        self.change_tempo(-1)

    def change_tempo(self, direction):
        """Increase/decrease tempo"""
        curr = self.tempo // self.BPM_STEP
        self.set_tempo((curr + direction) * self.BPM_STEP)


if __name__ == "__main__":
    Metronome().run()
