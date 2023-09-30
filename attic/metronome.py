#!/usr/bin/env python3
import argparse
from pathlib import Path
import signal
import time
import wave

import pyaudio


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
            "-b",
            "--beats-per-minute",
            type=int,
            default=90,
        )
        parser.add_argument(
            "-B",
            "--beats-per-bar",
            type=int,
            default=4,
        )
        args = parser.parse_args()

        with wave.open(str(args.click_hi), "rb") as wfo:
            channels = wfo.getnchannels()
            rate = wfo.getframerate()
            width = wfo.getsampwidth()
            hi_data = wfo.readframes(wfo.getnframes())
        with wave.open(str(args.click_lo), "rb") as wfo:
            lo_data = wfo.readframes(wfo.getnframes())

        beat_sec = 60 / args.beats_per_minute
        bars_per_loop = 10
        self.bytes_per_frame = channels * width
        loop_sec = bars_per_loop * args.beats_per_bar * beat_sec
        self.loop_size = int(loop_sec * rate * self.bytes_per_frame)
        self.loop = bytearray(self.loop_size)
        for n in range(bars_per_loop * args.beats_per_bar):
            data = hi_data if n % args.beats_per_bar == 0 else lo_data
            offset = int(n * beat_sec * rate) * self.bytes_per_frame
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
