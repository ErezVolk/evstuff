#!/usr/bin/env python3
import argparse
from pathlib import Path
import re
import signal
import time
import wave

import pyaudio
import pynput.keyboard
import Quartz

# TODO: Better than assert
# TODO: Support non-wav clicks
# TODO: Handle incompatible hi/lo
# TODO: memory
# TODO: support tempo=500


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


class Metronome:
    args: argparse.Namespace
    bytes_per_frame: int
    loop_size: int
    loop: bytearray
    offset: int
    aborting: bool = False
    paused: bool = False

    def parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "tempo",
            type=int,
            nargs="?",
            default=90,
        )
        parser.add_argument(
            "-C",
            "--click-hi",
            type=Path,
            default=HERE / "Perc_MetronomeQuartz_hi.wav",
        )
        parser.add_argument(
            "-c",
            "--click-lo",
            type=Path,
            default=HERE / "Perc_MetronomeQuartz_lo.wav",
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-b",
            "--beat",
            type=int,
            nargs="+",
            default=[4],
        )
        group.add_argument(
            "-r",
            "--rhythm",
            choices=["quarter", "eighth", "triple", "clave", "clave2"],
        )
        group.add_argument(
            "-s",
            "--subdivision",
            type=str,
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
        )
        self.args = parser.parse_args()

    def run(self):
        self.parse_args()

        self.read_clicks()
        self.figure_pattern()

        self.set_tempo(self.args.tempo)

        if self.args.debug:
            with wave.open("loop.wav", "wb") as wfo:
                wfo.setnchannels(self.channels)
                wfo.setframerate(self.rate)
                wfo.setsampwidth(self.width)
                wfo.writeframes(self.loop)

        # Exit cleanly on Ctrl-C
        signal.signal(signal.SIGINT, self.handle_ctrl_c)

        # Listen to Media keys
        self.media_keys = {
            NX_KEYTYPE_EJECT: self.handle_eject,
            NX_KEYTYPE_PLAY: self.handle_play_pause,
            NX_KEYTYPE_FAST: self.handle_fast_forward,
            NX_KEYTYPE_REWIND: self.handle_rewind,
        }
        listener = pynput.keyboard.Listener(darwin_intercept=self.intercept)
        listener._EVENTS = Quartz.CGEventMaskBit(Quartz.NSSystemDefined)
        listener.start()

        player = pyaudio.PyAudio()

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
        with wave.open(str(self.args.click_hi), "rb") as wfo:
            self.channels = wfo.getnchannels()
            self.rate = wfo.getframerate()
            self.width = wfo.getsampwidth()
            self.hi_data = wfo.readframes(wfo.getnframes())
        with wave.open(str(self.args.click_lo), "rb") as wfo:
            assert self.channels == wfo.getnchannels()
            assert self.rate == wfo.getframerate()
            assert self.width == wfo.getsampwidth()
            self.lo_data = wfo.readframes(wfo.getnframes())
        self.bytes_per_frame = self.channels * self.width

    def figure_pattern(self):
        los = []
        if self.args.subdivision:
            assert re.fullmatch(r"[-tT]+", self.args.subdivision)
            self.beats_per_bar = 1
            subs = len(self.args.subdivision)
            his = []
            los = []
            for n, c in enumerate(self.args.subdivision):
                if c == "T":
                    his.append(n / subs)
                elif c == "t":
                    los.append(n / subs)
        elif self.args.rhythm == "quarter":
            self.beats_per_bar = 1
            his = [0]
            los = []
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
            los = []
        elif self.args.rhythm == "clave2":
            self.beats_per_bar = 4
            his = [.5, 1, 2, 2.75, 3.5]
            los = []
        else:
            print(f"Beat: {self.args.beat}")
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

    def read_more(self, in_data, frame_count, time_info, status):
        if self.aborting or self.paused:
            return (b'', pyaudio.paAbort)

        nbytes = frame_count * self.bytes_per_frame
        chunks = []

        while nbytes > 0:
            chunk_nbytes = min(nbytes, len(self.loop) - self.offset)
            chunks.append(self.loop[self.offset:self.offset + chunk_nbytes])
            self.offset = (self.offset + chunk_nbytes) % len(self.loop)
            nbytes -= chunk_nbytes

        data = b''.join(chunks)
        return (data, pyaudio.paContinue)

    def set_tempo(self, tempo):
        self.tempo = min(200, max(20, tempo))
        self.make_loop()

    def make_loop(self):
        print(f"Tempo: ♩ = {self.tempo}")
        beat_sec = 60 / self.tempo
        ideal_bar_frames = self.beats_per_bar * beat_sec * self.rate
        ideal_bar = ideal_bar_frames * self.bytes_per_frame
        bars_per_loop = 1
        rounded_frames = round(ideal_bar / self.bytes_per_frame)
        self.loop_size = rounded_frames * self.bytes_per_frame

        self.loop = bytearray(self.loop_size)
        for n_bar in range(bars_per_loop):
            for pos, data in self.pattern.items():
                beat_n = (n_bar * self.beats_per_bar) + pos
                frame_n = beat_n * beat_sec * self.rate
                offset = round(frame_n) * self.bytes_per_frame
                self.loop[offset:offset + len(data)] = data
        self.offset = 0

    def handle_ctrl_c(self, sig, frame):
        """Handle Ctrl-C"""
        self.abort()

    def abort(self):
        print("Aborting...")
        self.aborting = True

    def intercept(self, event_type, event_ref):
        """Handle media key event"""
        event = Quartz.NSEvent.eventWithCGEvent_(event_ref)

        bitmap = event.data1()
        key = (bitmap & 0xffff0000) >> 16

        try:
            handler = self.media_keys[key]
        except KeyError:
            return event_ref

        is_press = ((bitmap & 0xff00) >> 8) == 0x0a
        if not is_press:  # React when on key release
            handler()

    def handle_eject(self):
        self.abort()

    def handle_play_pause(self):
        self.paused = not self.paused
        print(f"To {'restart' if self.paused else 'pause'}, press ⏯")

    def handle_fast_forward(self):
        self.change_tempo(1)

    def handle_rewind(self):
        self.change_tempo(-1)

    def change_tempo(self, direction):
        if not self.paused:
            print("Cannot change tempo while playing")
            return

        self.set_tempo(((self.tempo // 10) + direction) * 10)


if __name__ == "__main__":
    Metronome().run()
