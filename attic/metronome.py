#!/usr/bin/env python3
import argparse
from pathlib import Path
import signal
import time
import wave

import pyaudio

# TODO: Handle incompatible hi/lo


class Metronome:
    bytes_per_frame: int
    loop_size: int
    loop: bytearray
    offset: int
    stopping: bool = False

    def run(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-C",
            "--click-hi",
            type=Path,
            default=Path("clicks") / "Perc_MetronomeQuartz_hi.wav",
        )
        parser.add_argument(
            "-c",
            "--click-lo",
            type=Path,
            default=Path("clicks") / "Perc_MetronomeQuartz_lo.wav",
        )
        parser.add_argument(
            "-t",
            "--tempo",
            type=int,
            default=90,
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-b",
            "--beat",
            type=int,
            default=4,  # TODO: "3 2"
        )
        group.add_argument(
            "-r",
            "--rhythm",
            choices=["quarter", "eighth", "triple", "clave"],
        )
        # TODO: --rhythm quarter/eigth/clave...
        # TODO: interactive (tempo up/down...)
        args = parser.parse_args()

        with wave.open(str(args.click_hi), "rb") as wfo:
            channels = wfo.getnchannels()
            rate = wfo.getframerate()
            width = wfo.getsampwidth()
            hi_data = wfo.readframes(wfo.getnframes())
        with wave.open(str(args.click_lo), "rb") as wfo:
            assert channels == wfo.getnchannels()
            assert rate == wfo.getframerate()
            assert width == wfo.getsampwidth()
            lo_data = wfo.readframes(wfo.getnframes())

        beat_sec = 60 / args.tempo
        bars_per_loop = 10
        self.bytes_per_frame = channels * width

        print(f"Tempo: ♩ = {args.tempo}")
        los = []
        if args.rhythm == "quarter":
            beats_per_bar = 1
            his = [0]
            los = []
        elif args.rhythm == "eighth":
            beats_per_bar = 1
            his = [0]
            los = [.5]
        elif args.rhythm == "triple":
            beats_per_bar = 1
            his = [0]
            los = [1 / 3, 2 / 3]
        elif args.rhythm == "clave":
            beats_per_bar = 8
            his = [0, 1.5, 3, 5, 6]
            los = []
        else:
            print(f"Beat: {args.beat}")
            beats_per_bar = max(1, args.beat)
            his = [0]
            los = range(1, beats_per_bar)

        events = {
            pos: data
            for data, positions in ((hi_data, his), (lo_data, los))
            for pos in positions
        }

        loop_sec = bars_per_loop * beats_per_bar * beat_sec
        self.loop_size = int(loop_sec * rate * self.bytes_per_frame)
        self.loop = bytearray(self.loop_size)
        for n_bar in range(bars_per_loop):
            for pos, data in events.items():
                beat_n = (n_bar * beats_per_bar) + pos
                offset = int(beat_n * beat_sec * rate) * self.bytes_per_frame
                self.loop[offset:offset + len(data)] = data
        self.offset = 0

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
        print("\nAborting...")
        self.stopping = True


if __name__ == "__main__":
    Metronome().run()
