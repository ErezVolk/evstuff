#!/usr/bin/env python3
"""A simple metronome"""
import argparse
from pathlib import Path
import re
import signal
import time
import typing as t

from soundfile import SoundFile
import pyaudio
import rich.live

try:
    import pynput.keyboard
    from Quartz import CGEventMaskBit
    from Quartz import NSEvent
    from Quartz import NSSystemDefined

    # pylint: disable-next=too-few-public-methods
    class MiniListener(pynput.keyboard.Listener):
        """A Listener that only cares about media keys"""
        _EVENTS = CGEventMaskBit(NSSystemDefined)

    WITH_MEDIA_KEYS = True
except ImportError:
    print("Warning: No media key support")
    WITH_MEDIA_KEYS = False

# TODO: Test, don't assert
# TODO: Handle incompatible hi-lo
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
    def __init__(self, data: bytes | bytearray):
        self.data = data
        self.offset = 0

    def get(self, nbytes: int) -> bytes:
        """Get another chunk"""
        limit = min(self.offset + nbytes, len(self.data))
        chunk = self.data[self.offset:limit]
        self.offset = limit % len(self.data)
        return chunk

    def may_flip(self) -> bool:
        """Are we at a good point to flip to the next loop"""
        return self.offset == 0


# pylint: disable-next=too-many-instance-attributes
class Metronome:
    """A simple metronome"""
    args: argparse.Namespace
    status: rich.live.Live
    bytes_per_frame: int
    loop: ByteLoop | None = None
    next_loop: ByteLoop | None = None
    aborting: bool = False
    paused: bool = True
    media_keys: dict[int, t.Callable]
    channels: int
    rate: int
    width: int
    hi_data: bytes
    lo_data: bytes
    beats_per_bar: int
    pattern: dict[int, bytes]
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
            "--beat",
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
                "e.g., 't-t' is a first- and third triplet "
                "beat, and '-t' clicks on the second eighth. "
                "'T' = high click; 't' = low click; '-' = rest."
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
        try:
            beat = int(arg)
        except ValueError:
            raise argparse.ArgumentTypeError("must be a positive number")
        if beat > 0:
            return beat
        raise argparse.ArgumentTypeError("must be positive")

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
        with SoundFile(str(paths[0])) as sfo:
            self.channels = sfo.channels
            self.rate = sfo.samplerate
            self.width = 2
            self.hi_data = sfo.buffer_read(dtype='int16')
        if len(paths) > 1:
            with SoundFile(str(paths[1])) as sfo:
                assert sfo.channels == self.channels
                assert sfo.samplerate == self.rate
                self.lo_data = sfo.buffer_read(dtype='int16')
        else:
            self.lo_data = self.hi_data
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
            assert all(beat > 0 for beat in self.args.beat)
            his = []
            self.beats_per_bar = 0
            for beat in self.args.beat:
                his.append(self.beats_per_bar)
                self.beats_per_bar += beat
            los = range(self.beats_per_bar)  # Will get overrun by his

        self.pattern = {
            pos: data
            for data, positions in ((self.lo_data, los), (self.hi_data, his))
            for pos in positions
        }

    # pylint: disable-next=unused-argument
    def read_more(self, in_data, frame_count, time_info, status):
        """Supply pyaudio with more audio"""
        if self.aborting or self.paused:
            return (b'', pyaudio.paAbort)

        nbytes = frame_count * self.bytes_per_frame
        chunks = []

        while nbytes > 0 and not self.paused:
            if self.next_loop is not None:
                if self.loop.may_flip():
                    self.loop = self.next_loop
                    self.next_loop = None

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

        loop = bytearray(loop_size)
        for n_bar in range(bars_per_loop):
            for pos, data in self.pattern.items():
                beat_n = (n_bar * self.beats_per_bar) + pos
                frame_n = beat_n * beat_sec * self.rate
                offset = round(frame_n) * self.bytes_per_frame
                loop[offset:offset + len(data)] = data

        if self.loop is None:
            self.loop = ByteLoop(loop)
        else:
            self.next_loop = ByteLoop(loop)
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
        """Handle media key event"""
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
            suffix = " (PAUSED)"
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
