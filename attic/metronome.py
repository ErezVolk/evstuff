#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
import re
import signal
import time
import wave

import pyaudio
import rich.logging

# TODO: Better than assert
# TODO: Support non-wav clicks
# TODO: Handle incompatible hi/lo
# TODO: memory
# TODO: interactive (tempo up/down...), maybe with Textual
# TODO: tempo=500


# Metronome sounds recorded by Ludwig Peter Müller (muellerwig@gmail.com)
# and distribution under the Creative Commons CC0 1.0 Universal license.

THIS = Path(__file__).resolve()
HERE = THIS.parent


class Metronome:
    args: argparse.Namespace
    log: logging.Logger
    bytes_per_frame: int
    loop_size: int
    loop: bytearray
    offset: int
    stopping: bool = False

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

        assert self.args.tempo > 0

    def configure_logging(self):
        """Set logging format and level"""
        if self.args.debug:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.basicConfig(
            format="%(message)s",
            datefmt="[%X]",
            level=level,
            handlers=[rich.logging.RichHandler()],
        )
        self.log = logging.getLogger(THIS.stem)

    def run(self):
        self.parse_args()
        self.configure_logging()

        with wave.open(str(self.args.click_hi), "rb") as wfo:
            channels = wfo.getnchannels()
            rate = wfo.getframerate()
            width = wfo.getsampwidth()
            hi_data = wfo.readframes(wfo.getnframes())
        with wave.open(str(self.args.click_lo), "rb") as wfo:
            assert channels == wfo.getnchannels()
            assert rate == wfo.getframerate()
            assert width == wfo.getsampwidth()
            lo_data = wfo.readframes(wfo.getnframes())

        beat_sec = 60 / self.args.tempo
        self.bytes_per_frame = channels * width

        self.log.info(f"Tempo: ♩ = {self.args.tempo}")
        los = []
        if self.args.subdivision:
            assert re.fullmatch(r"[-tT]+", self.args.subdivision)
            beats_per_bar = 1
            subs = len(self.args.subdivision)
            his = []
            los = []
            for n, c in enumerate(self.args.subdivision):
                if c == "T":
                    his.append(n / subs)
                elif c == "t":
                    los.append(n / subs)
        elif self.args.rhythm == "quarter":
            beats_per_bar = 1
            his = [0]
            los = []
        elif self.args.rhythm == "eighth":
            beats_per_bar = 1
            his = [0]
            los = [.5]
        elif self.args.rhythm == "triple":
            beats_per_bar = 1
            his = [0]
            los = [1 / 3, 2 / 3]
        elif self.args.rhythm == "clave":
            beats_per_bar = 4
            his = [0, .75, 1.5, 2.5, 3]
            los = []
        elif self.args.rhythm == "clave2":
            beats_per_bar = 4
            his = [.5, 1, 2, 2.75, 3.5]
            los = []
        else:
            self.log.info(f"Beat: {self.args.beat}")
            assert all(beat > 0 for beat in self.args.beat)
            his = []
            beats_per_bar = 0
            for beat in self.args.beat:
                his.append(beats_per_bar)
                beats_per_bar += beat
            los = range(beats_per_bar)  # Will get overrun by his

        events = {
            pos: data
            for data, positions in ((lo_data, los), (hi_data, his))
            for pos in positions
        }

        ideal_bar = beats_per_bar * beat_sec * rate * self.bytes_per_frame
        bars_per_loop = 1
        rounded_frames = round(ideal_bar / self.bytes_per_frame)
        self.loop_size = rounded_frames * self.bytes_per_frame

        self.loop = bytearray(self.loop_size)
        for n_bar in range(bars_per_loop):
            for pos, data in events.items():
                beat_n = (n_bar * beats_per_bar) + pos
                offset = round(beat_n * beat_sec * rate) * self.bytes_per_frame
                self.loop[offset:offset + len(data)] = data
        self.offset = 0

        if self.args.debug:
            with wave.open("loop.wav", "wb") as wfo:
                wfo.setnchannels(channels)
                wfo.setframerate(rate)
                wfo.setsampwidth(width)
                wfo.writeframes(self.loop)

        signal.signal(signal.SIGINT, self.stop)

        player = pyaudio.PyAudio()
        stream = player.open(
            format=player.get_format_from_width(width),
            channels=channels,
            rate=rate,
            output=True,
            stream_callback=self.read_more,
        )

        while stream.is_active():
            time.sleep(.1)

        stream.close()
        player.terminate()

    def read_more(self, in_data, frame_count, time_info, status):
        if self.stopping:
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

    def stop(self, sig, frame):
        self.log.info("Aborting...")
        self.stopping = True


if __name__ == "__main__":
    Metronome().run()
