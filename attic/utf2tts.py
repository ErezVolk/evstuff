#!/usr/bin/env python3
"""UTF-8 to audiobook"""
import argparse
import html
from pathlib import Path
import re
import subprocess
import sys

import pandas as pd

try:
    from google.cloud import texttospeech as gg_tts
    HAVE_GOOGLE = True
except ImportError:
    HAVE_GOOGLE = False

PAUSE_TO_GAP_MS = {3: 4000, 2: 3000, 1: 1000}


class Utf2Tts:
    """UTF-8 to audiobook"""
    def parse_args(self):
        """Command-line arguments"""
        parser = argparse.ArgumentParser()
        parser.add_argument("input", type=Path, nargs="?", help="Input UTF-8 file")
        parser.add_argument("-d", "--debug", action="store_true")

        group = parser.add_mutually_exclusive_group()
        group.add_argument("-v", "--macos-voice", help="Generate audiobook using MacOS")
        if HAVE_GOOGLE:
            group.add_argument(
                "-g", "--google-voice", help="Generate audiobook using Google"
            )

        parser.add_argument("-s", "--stem", help="Audio filename prefix")

        parser.add_argument(
            "--force", action="store_true", help="Generate audio even if file exists"
        )
        parser.add_argument("-S", "--suffix", default="mp3")
        parser.add_argument("--small-delta", default=0.55)
        parser.add_argument("--big-delta", default=5)
        parser.add_argument("--rate")
        parser.add_argument("--max-files", type=int)

        self.parser = parser
        self.args = parser.parse_args()

    parser: argparse.ArgumentParser
    args: argparse.Namespace
    preamble: str
    n_files: int = 0
    gg_client: object | None = None
    gg_voice: object
    gg_audio: object

    def main(self):
        self.parse_args()

        if HAVE_GOOGLE:
            if self.args.google_voice and self.args.google_voice.endswith("?"):
                self.list_google_voices()
                return

        with open(self.args.input, "r", encoding="utf-8") as ifo:
            tosay = pd.DataFrame({
                "text": [line.strip() for line in ifo]
            })
        tosay["lineno"] = tosay.index + 1
        tosay.drop(tosay.index[tosay.text == ""], inplace=True)
        tosay.loc[tosay.text.str.fullmatch(r"\d+"), "chap"] = tosay.text
        tosay["n_words"] = tosay.text.str.split(r"\s", regex=True).str.len()
        tosay["chap"] = tosay.chap.fillna(method="ffill").fillna("0").astype(int)
        tosay["pause"] = tosay.lineno.diff().map(lambda diff: 1 if diff <= 2 else 2 if diff <= 4 else 3)

        if self.args.macos_voice:
            self.preamble = f"[[rate {int(self.args.rate)}]] " if self.args.rate else ""
            tts = self.macos_tts
        elif HAVE_GOOGLE and self.args.google_voice:
            tts = self.google_tts
        else:
            print("Not creating audiobook")
            return

        print(f"Number of paragraphs: {len(tosay)}")
        stem = self.args.stem or self.args.input.stem
        for chap, group in tosay.groupby("chap"):
            path = self.args.input.with_name(f"{stem}-{chap:04d}.{self.args.suffix}")
            if self.args.force or not path.is_file():
                tts(rows=group, path=path)

    def macos_tts(self, rows: pd.DataFrame, path: Path):
        """TTS using MacOS's `say (1)` and `sox`."""
        aiff = path.with_suffix(".aiff")
        text = " ".join(
            f"{self.preamble}[[slnc 600]] {row.text} [[slnc {PAUSE_TO_GAP_MS[row.pause] - 600}]]"
            for _, row in rows.iterrows()
        )
        subprocess.run(
            [
                "say",
                "-v",
                self.args.macos_voice,
                "-o",
                str(aiff),
                text,
            ],
            check=True,
        )
        self.sox_and_rm(aiff, path)

    def sox_and_rm(self, curr: Path, path: Path):
        """Run sox to convert an audio file and delete the original"""
        if curr != path:
            subprocess.run(["sox", str(curr), str(path)], check=True)
            curr.unlink()

        print(f"... {path} {path.stat().st_size:,} Bytes")

        self.n_files += 1
        if self.args.max_files:
            if self.n_files >= self.args.max_files:
                print("Reached maximum number of files.")
                sys.exit(0)

    def list_google_voices(self):
        """List Google cloud voices"""
        prefix = self.args.google_voice[:-1]
        print(f"Asking Google for voices starting with {repr(prefix)}...")
        client = gg_tts.TextToSpeechClient()
        for voice in client.list_voices().voices:
            if any(lang.startswith(prefix) for lang in voice.language_codes):
                print(
                    voice.name,
                    voice.ssml_gender.name,
                    "".join(voice.language_codes),
                )

    def google_tts(self, rows: pd.DataFrame, path: Path):
        """TTS using Google cloud.

        There's a "synthesize long audio" API, but that requires creating
        a bucket and all that.
        """
        if self.gg_client is None:
            name = self.args.google_voice
            self.gg_client = gg_tts.TextToSpeechClient()
            self.gg_voice = gg_tts.VoiceSelectionParams(
                name=name,
                language_code=re.sub(r"^([a-z][a-z]-[A-Z][A-Z])", r"\1", name),
            )
            self.gg_audio = gg_tts.AudioConfig(
                audio_encoding=gg_tts.AudioEncoding.MP3,
                speaking_rate=float(self.args.rate) or 1.0,
            )

        mp3 = path.with_suffix(".mp3")
        print(f"{path.name} (words={rows.n_words.sum()}) ...")
        with open(mp3, "wb") as ofo:
            for _, row in rows.iterrows():
                ssml = (
                    f'<speak>{html.escape(row.text)}</speak>'
                    f'<break time="{PAUSE_TO_GAP_MS[row.pause]}ms"/>'
                )
                response = self.gg_client.synthesize_speech(request={
                    "voice": self.gg_voice,
                    "audio_config": self.gg_audio,
                    "input": gg_tts.SynthesisInput(ssml=ssml),
                })
                ofo.write(response.audio_content)

        self.sox_and_rm(mp3, path)


if __name__ == "__main__":
    Utf2Tts().main()
