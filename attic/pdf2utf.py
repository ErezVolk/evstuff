#!/usr/bin/env -S uv run --script
"""PDF to UTF-8 and audiobook (WIP)."""

__TODO__ = """
- U+2011 NON-BREAKING-HYPHEN should consume all preceding whitespace (Jorge)
- repeating header/footer (Jorge)
"""

import argparse
import html
import re
import subprocess
import typing as t
from pathlib import Path

import numpy as np
import pandas as pd  # ty: ignore[unresolved-import]
import pymupdf  # ty: ignore[unresolved-import]
from google.cloud import texttospeech as gg_tts  # ty: ignore[unresolved-import]

PAUSE_TO_GAP_MS = {3: 4000, 2: 3000, 1: 1000}
PAUSE_TO_MIN_WORDS = {3: 1, 2: 5, 1: 20}
THIS = Path(__file__).stem
NON_LOWER_RE = r"[^a-z\xDF-\xF6\xF8-\xFF]"
HEADER_RE = f"{NON_LOWER_RE}*[A-Z]{NON_LOWER_RE}*"
HYPHENS = ["\xad", "\u20a0", "\u2011", "-"]


class Pdf2Utf:
    """PDF to UTF-8 and audiobook (WIP)."""

    parser: argparse.ArgumentParser
    args: argparse.Namespace
    gg_client: object | None = None
    gg_voice: object
    gg_audio: object
    ddump_no: int = 0

    LEFT_MARGIN_PAUSE = 15
    INTER_PARA_PAUSE = 30

    def parse_args(self) -> None:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument("input", type=Path, nargs="?", help="Input PDF file")
        parser.add_argument("output", type=Path, nargs="?", help="Output text file")
        parser.add_argument(
            "-f", "--first-page", type=int, help="First page to convert"
        )
        parser.add_argument("-l", "--last-page", type=int, help="Last page to convert")
        parser.add_argument("-d", "--debug", action="store_true")

        group = parser.add_mutually_exclusive_group()
        group.add_argument("-v", "--macos-voice", help="Generate audiobook using MacOS")
        group.add_argument(
            "-g", "--google-voice", help="Generate audiobook using Google"
        )

        parser.add_argument("-s", "--stem", help="Audio filename prefix")

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--first-paragraph", type=int, help="First audio paragraph number"
        )
        group.add_argument(
            "--first-prefix", type=str, help="First audio paragraph prefix"
        )

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--last-paragraph", type=int, help="Last audio paragraph number"
        )
        group.add_argument(
            "--last-prefix", type=str, help="Last audio paragraph prefix"
        )
        group.add_argument("--max-paragraphs", type=int)

        parser.add_argument(
            "--force", action="store_true", help="Generate audio even if file exists"
        )
        parser.add_argument("-S", "--suffix", default="mp3")
        parser.add_argument("--small-delta", default=0.55)
        parser.add_argument("--big-delta", default=5)

        parser.add_argument(
            "--top", type=float, default=0.0, help="Extra top margin (pt)"
        )
        parser.add_argument(
            "--bottom", type=float, default=0.0, help="Extra bottom margin (pt)"
        )

        self.parser = parser
        self.args = parser.parse_args()

    def main(self) -> None:  # noqa: C901, PLR0915, PLR0912
        """Do it."""
        self.parse_args()

        if not self.args.input:
            candidates = list(Path.cwd().glob("*.pdf"))
            if len(candidates) != 1:
                self.parser.error("Unable to guess input file name")

            (self.args.input,) = candidates
            input(f"Press Enter to process {self.args.input.name!r}...")

        if not self.args.output:
            self.args.output = self.args.input.with_suffix(".utf8")

        if self.args.google_voice and self.args.google_voice.endswith("?"):
            self.list_google_voices()
            return

        print(f"Reading {self.args.input}")
        words = self.read_words()

        book = (
            words.groupby(["page_no", "page_label", "rounded_bottom"])
            .apply(
                lambda group: pd.Series(
                    {
                        "left": group.left.min(),
                        "right": group.right.max(),
                        "top": group.top.max(),
                        "bottom": group.bottom.min(),
                        "text": " ".join(group.word),
                    }
                )
            )
            .reset_index()
        )

        book["odd"] = (book.page_no % 2) == 1
        book["height"] = book.bottom - book.top

        self.ddump(book, "raw")

        if self.args.first_page:
            book = book.drop(book.index[book.page_no < self.args.first_page])
        if self.args.last_page:
            book = book.drop(book.index[book.page_no > self.args.last_page])

        # Lose printer's marks and page numbers (not very generic)
        book = book.drop(book.index[book.text.str.contains(".indd")])
        book = book.drop(book.index[book.text == book.page_label])

        common_height = book.height - self.most_common(book.height)
        book["bigness"] = common_height.map(
            lambda h: (
                "s"
                if h < -self.args.small_delta
                else "n"
                if h < self.args.big_delta
                else "l"  # Allende
            )
        )
        for bigness in book.bigness.unique():
            tmap = book.bigness == bigness
            book.loc[tmap, "left_margin"] = (
                book[tmap].groupby("page_no").left.transform("min")
            )

        self.ddump(book, "culled")

        # Merge drop caps (Allende)
        drop_cap_tmap = (book.bigness == "l") & (book.text.str.len() == 1)
        for loc in book.index[drop_cap_tmap]:
            drop_row = book.loc[loc]
            overlap_tmap = book.page_no == drop_row.page_no
            overlap_tmap &= book.bigness != "l"
            overlap_tmap &= book.top.between(drop_row.top, drop_row.bottom)
            if overlap_tmap.sum() == 0:
                continue
            top_idx = book[overlap_tmap].top.idxmin()
            book.loc[overlap_tmap, "left"] = book.loc[top_idx, "left_margin"]
            book.loc[top_idx, "text"] = f"{drop_row.text}{book.loc[top_idx, 'text']}"
        book = book.drop(book.index[drop_cap_tmap])

        # Remove empty lines
        book = book.drop(book.index[book.text == ""])

        # Remove line numbers (TODO: Allende, risky, insufficient)
        book = book.drop(book.index[book.text == book.page_label])

        book["from_prev"] = book.groupby("page_no").bottom.diff()

        common_first_bottom = self.most_common(book.groupby("page_no").bottom.min())
        common_last_bottom = self.most_common(book.groupby("page_no").bottom.max())
        book["from_first_bottom"] = book.bottom - common_first_bottom
        book["from_last_bottom"] = common_last_bottom - book.bottom

        book["first_in_page"] = first_tmap = book.from_prev.isna()
        book.loc[first_tmap, "from_prev"] = (
            book[first_tmap].bottom - common_first_bottom
        )
        self.ddump(book, "pre-merge")

        # Dehyphenate some more
        hyphen_tmap = book.text.str[-1].isin(HYPHENS)
        hyphen_labels = book.index[hyphen_tmap][::-1]
        joinee_labels = book.index[hyphen_tmap.shift(1, fill_value=False)][::-1]
        drop_labels = []
        hyphen_joinee_labels = zip(hyphen_labels, joinee_labels, strict=True)
        for hyphen_label, joinee_label in hyphen_joinee_labels:
            hyphen_row = book.loc[hyphen_label]
            joinee_row = book.loc[joinee_label]
            both = book.loc[hyphen_label : joinee_label + 1]
            book.loc[hyphen_label, "text"] = hyphen_row.text[:-1] + joinee_row.text
            if hyphen_row.page_no == joinee_row.page_no:
                book.loc[hyphen_label, "top"] = both.top.min()
                book.loc[hyphen_label, "left"] = both.left.min()
                book.loc[hyphen_label, "right"] = both.right.max()
                book.loc[hyphen_label, "bottom"] = both.bottom.max()
            drop_labels.append(joinee_label)
        book = book.drop(drop_labels)

        self.ddump(book, "dehyphenated")

        book["from_left"] = book.left - book.left_margin

        header_tmap = book.text.str.fullmatch(HEADER_RE)
        header_tmap |= (book.bigness == "l") & (book.bigness.shift(1) != "l")
        header_tmap &= book.first_in_page
        book["header"] = header_tmap

        book["pause"] = 0
        book.loc[book.from_left > self.LEFT_MARGIN_PAUSE, "pause"] = 1  # Allende
        book.loc[book.from_prev > self.INTER_PARA_PAUSE, "pause"] = 2  # Allende
        book.loc[header_tmap, "pause"] = 3  # Heuristic
        para_tmap = book.pause > 0
        para_tmap.iloc[0] = True

        book.loc[para_tmap, "para"] = np.arange(1, para_tmap.sum() + 1)
        book.para = book.para.ffill().astype(int)

        self.ddump(book, "pre-paras")

        paras = book.groupby("para").text.apply(" ".join).to_frame("text")
        paras = paras.set_index(np.arange(len(paras)) + 1)
        paras["pause"] = book[para_tmap].pause.shift(-1, fill_value=2).to_numpy()
        paras["n_words"] = paras.text.str.split(r"\s", regex=True).str.len()

        # Chapter numbers (of a sort)
        paras["header"] = book[para_tmap].header.to_numpy()
        paras.loc[paras.index[0], "header"] = True
        paras.loc[paras.header, "chap"] = np.arange(paras.header.sum()) + 1
        paras.chap = paras.chap.ffill().astype(int)
        self.ddump(paras, "paras")

        print(f"Writing {self.args.output}")
        with self.args.output.open("w", encoding="UTF-8") as fobj:
            for _, row in paras.iterrows():
                fobj.write(row.text)
                fobj.write("\n\n" * row.pause)

        if self.args.macos_voice:
            self.convert(paras, self.macos_tts)
        elif self.args.google_voice:
            self.convert(paras, self.google_tts)
        elif self.args.debug:
            print("Not creating audiobook")

    def read_words(self) -> pd.DataFrame:
        """Read the words."""
        doc = pymupdf.Document(self.args.input)
        words = pd.DataFrame.from_records(
            [
                [page_no, page.get_label() or str(page_no), * rec]
                for page_no, page in enumerate(doc, 1)
                for rec in self.get_page_text(page)
            ],
            columns=[
                "page_no",
                "page_label",
                "left",
                "top",
                "right",
                "bottom",
                "word",
                "block_no",
                "line_no",
                "word_no",
            ],
        )
        words["rounded_bottom"] = (words.bottom / 10).round() * 10  # Allende

        self.ddump(words, "words")
        return words

    def get_page_text(self, page: pymupdf.Page) -> t.Iterable[tuple]:
        """Get text in the relevant area of the page."""
        box = page.trimbox
        clip = pymupdf.Rect(
            box.x0,
            box.y0 + self.args.top,
            box.x1,
            box.y1 - self.args.bottom,
        )
        return page.get_text("words", clip=clip)

    def convert(self, paras: pd.DataFrame, tts: t.Callable) -> None:
        """Convert text to audio."""
        tosay = paras
        if self.args.first_prefix:
            self.args.first_paragraph = paras.index[
                paras.text.str.startswith(self.args.first_prefix)
            ][0]
        if self.args.first_paragraph:
            tosay = tosay.loc[tosay.index >= self.args.first_paragraph]

        if self.args.last_prefix:
            self.args.last_paragraph = paras.index[
                paras.text.str.startswith(self.args.last_prefix)
            ][0]
        if self.args.last_paragraph:
            tosay = tosay.loc[tosay.index <= self.args.last_paragraph]

        if self.args.max_paragraphs:
            tosay = tosay.iloc[: self.args.max_paragraphs]

        desc = [f"paragraphs: {len(tosay)}"]
        if len(tosay) < len(paras):
            desc.append(f" of {len(paras)}")
        desc.append(f"; chapters: {tosay.chap.nunique()}")
        print(f"TTS ({''.join(desc)})")
        stem = self.args.stem or self.args.output.stem
        for chap, group in tosay.groupby("chap"):
            path = self.args.output.with_name(f"{stem}-{chap:04d}.{self.args.suffix}")
            if self.args.force or not path.is_file():
                tts(rows=group, path=path)

    def macos_tts(self, rows: pd.DataFrame, path: Path) -> None:
        """TTS using MacOS's `say (1)` and `sox`."""
        aiff = path.with_suffix(".aiff")
        text = " ".join(
            f"[[slnc 600]] {row.text} [[slnc {PAUSE_TO_GAP_MS[row.pause] - 600}]]"
            for _, row in rows.iterrows()
        )
        cmd = [
            "say",
            "-v",
            self.args.macos_voice,
            "-o",
            str(aiff),
            text,
        ]
        subprocess.run(cmd, check=True)
        self.sox_and_rm(aiff, path)

    def sox_and_rm(self, curr: Path, path: Path) -> None:
        """Run sox to convert an audio file and delete the original."""
        if curr == path:
            return
        cmd = ["sox", str(curr), str(path)]
        subprocess.run(cmd, check=True)
        curr.unlink()

    def list_google_voices(self) -> None:
        """List Google cloud voices."""
        prefix = self.args.google_voice[:-1]
        print(f"Asking Google for voices starting with {prefix!r}...")
        client = gg_tts.TextToSpeechClient()
        for voice in client.list_voices().voices:
            if any(lang.startswith(prefix) for lang in voice.language_codes):
                print(
                    voice.name,
                    voice.ssml_gender.name,
                    "".join(voice.language_codes),
                )

    def google_tts(self, rows: pd.DataFrame, path: Path) -> None:
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
            self.gg_audio = gg_tts.AudioConfig(audio_encoding=gg_tts.AudioEncoding.MP3)
        assert isinstance(self.gg_client, gg_tts.TextToSpeechClient)

        mp3 = path.with_suffix(".mp3")
        print(f"{path.name} (words={rows.n_words.sum()}) ...")
        with mp3.open("wb") as ofo:
            for _, row in rows.iterrows():
                ssml = (
                    f"<speak>{html.escape(row.text)}</speak>"
                    f'<break time="{PAUSE_TO_GAP_MS[row.pause]}ms"/>'
                )
                response = self.gg_client.synthesize_speech(
                    request={
                        "voice": self.gg_voice,
                        "audio_config": self.gg_audio,
                        "input": gg_tts.SynthesisInput(ssml=ssml),
                    }
                )
                ofo.write(response.audio_content)

        self.sox_and_rm(mp3, path)
        print(f"... {path.stat().st_size:,} Bytes")

    def ddump(self, obj: pd.DataFrame, name: str) -> None:
        """Debug dump of an object."""
        if not self.args.debug:
            return

        self.ddump_no += 1
        path = self.args.output.parent / f"debug-{THIS}-{self.ddump_no:02d}-{name}"
        path = path.with_suffix(".parquet")
        print(f"(debug) Writing {path}")
        obj.to_parquet(path)

    @classmethod
    def most_common(cls, series: pd.Series) -> float:
        """Make an approximation."""
        return float(series.round(1).mode()[0])


if __name__ == "__main__":
    Pdf2Utf().main()

# /// script
# dependencies = ["pymupdf", "google-cloud-texttospeech", "numpy", "pandas"]
# ///
