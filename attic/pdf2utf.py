#!/usr/bin/env python3
"""Currently only geared to a specific PDF"""
import argparse
import html
from pathlib import Path
import pickle
import re
import subprocess

import numpy as np
import pandas as pd
import fitz


PAUSE_TO_GAP_MS = {2: 3000, 1: 1000, 0: 0}
THIS = Path(__file__).stem
NON_LOWER_RE = r"[^a-z\xDF-\xF6\xF8-\xFF]"
HEADER_RE = f"{NON_LOWER_RE}*[A-Z]{NON_LOWER_RE}*"
HYPHENS = ["\xad", "\u20a0", "\u2011", "-"]


class Pdf2Utf():
    gstate = {}

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("input", type=Path, nargs="?", help="Input PDF file")
        parser.add_argument("output", type=Path, nargs="?", help="Output text file")
        parser.add_argument("-f", "--first-page", type=int, help="First page to convert")
        parser.add_argument("-l", "--last-page", type=int, help="Last page to convert")
        parser.add_argument("-d", "--debug", action="store_true")

        group = parser.add_mutually_exclusive_group()
        group.add_argument("-v", "--macos-voice", help="Generate audiobook using MacOS")
        group.add_argument("-g", "--google-voice", help="Generate audiobook using Google")

        parser.add_argument("-s", "--stem", help="Audio filename prefix")

        group = parser.add_mutually_exclusive_group()
        group.add_argument("--first-paragraph", type=int, help="First audio paragraph number")
        group.add_argument("--first-prefix", type=str, help="First audio paragraph prefix")

        group = parser.add_mutually_exclusive_group()
        group.add_argument("--last-paragraph", type=int, help="Last audio paragraph number")
        group.add_argument("--last-prefix", type=str, help="Last audio paragraph prefix")
        group.add_argument("--max-paragraphs", type=int)

        parser.add_argument("--force", action="store_true", help="Generate audio even if file exists")
        parser.add_argument("-u", "--unit", choices=["word", "block"], default="word")
        self.args = parser.parse_args()

        if not self.args.input:
            candidates = list(Path.cwd().glob("*.pdf"))
            if len(candidates) != 1:
                parser.error("Unable to guess input file name")

            (self.args.input,) = candidates
            input(f"Press Enter to process {repr(self.args.input.name)}...")

        if not self.args.output:
            self.args.output = self.args.input.with_suffix(".utf8")

        if self.args.google_voice and self.args.google_voice.endswith("?"):
            self.list_google_voices()
            return

        print(f"Reading {self.args.input}")
        doc = fitz.Document(self.args.input)
        if self.args.unit == "word":
            words = pd.DataFrame.from_records(
                [
                    [page_no, page.get_label() or str(page_no)] + list(rec)
                    for page_no, page in enumerate(doc, 1)
                    for rec in page.get_text("words", clip=page.trimbox)
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

            self.ddump(words, "words")

            words["rounded_bottom"] = (words.bottom / 10).round() * 10  # Allende
            book = words.groupby(
                ["page_no", "page_label", "rounded_bottom"]
            ).apply(lambda group: pd.Series({
                "left": group.left.min(),
                "right": group.right.max(),
                "top": group.top.max(),
                "bottom": group.bottom.min(),
                "text": " ".join(group.word),
            })).reset_index()
        elif self.args.unit == "block":
            book = pd.DataFrame([
                {
                    "page_no": page_number,
                    "page_label": page.get_label() or str(page_number),
                    "block": block[5],
                    "left": block[0],
                    "top": block[1],
                    "right": block[2],
                    "bottom": block[3],
                    "text": block[4].strip(),
                } for page_number, page in enumerate(doc, 1)
                for block in page.get_text(
                    "blocks",
                    clip=page.trimbox,
                    flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_WHITESPACE,
                )
            ])

        book["odd"] = (book.page_no % 2) == 1
        book["height"] = book.bottom - book.top

        self.ddump(book, "raw")

        if self.args.first_page:
            book.drop(book.index[book.page_no < self.args.first_page], inplace=True)
        if self.args.last_page:
            book.drop(book.index[book.page_no > self.args.last_page], inplace=True)

        # Lose printer's marks and page numbers (not very generic)
        book.drop(book.index[book.text.str.contains(".indd")], inplace=True)
        book.drop(book.index[book.text == book.page_label], inplace=True)

        common_height = book.height - self.most_common(book.height)
        book["bigness"] = common_height.map(
            lambda h: "s" if h < -1 else "n" if h < 5 else "l"  # Allende
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
            top_idx = book[overlap_tmap].top.idxmin()
            book.loc[overlap_tmap, "left"] = book.at[top_idx, "left_margin"]
            book.at[top_idx, "text"] = f"{drop_row.text}{book.at[top_idx, 'text']}"
        book.drop(book.index[drop_cap_tmap], inplace=True)

        # Remove empty lines
        book.drop(book.index[book.text == ""], inplace=True)

        # Remove line numbers (TODO: risky, insufficient)
        book.drop(book.index[book.text == book.page_label], inplace=True)

        # Allende-specific
        book.drop(book.index[book.text.str.contains("\n")], inplace=True)
        book.drop(book.index[book.bigness == "l"], inplace=True)

        book["from_prev"] = book.groupby("page_no").bottom.diff()

        common_first_bottom = self.most_common(book.groupby("page_no").bottom.min())
        common_last_bottom = self.most_common(book.groupby("page_no").bottom.max())
        book["from_first_bottom"] = book.bottom - common_first_bottom
        book["from_last_bottom"] = common_last_bottom - book.bottom

        book["first_in_page"] = first_tmap = book.from_prev.isna()
        book.loc[first_tmap, "from_prev"] = book[first_tmap].bottom - common_first_bottom
        self.ddump(book, "pre-merge")

        # Dehyphenate some more
        hyphen_tmap = book.text.str[-1].isin(HYPHENS)
        hyphen_labels = book.index[hyphen_tmap][::-1]
        joinee_labels = book.index[hyphen_tmap.shift(1, fill_value=False)][::-1]
        drop_labels = []
        for hyphen_label, joinee_label in zip(hyphen_labels, joinee_labels):
            hyphen_row = book.loc[hyphen_label]
            joinee_row = book.loc[joinee_label]
            both = book.loc[hyphen_label : joinee_label + 1]
            book.at[hyphen_label, "text"] = hyphen_row.text[:-1] + joinee_row.text
            if hyphen_row.page_no == joinee_row.page_no:
                book.at[hyphen_label, "top"] = both.top.min()
                book.at[hyphen_label, "left"] = both.left.min()
                book.at[hyphen_label, "right"] = both.right.max()
                book.at[hyphen_label, "bottom"] = both.bottom.max()
            drop_labels.append(joinee_label)
        book.drop(drop_labels, inplace=True)

        self.ddump(book, "dehyphenated")

        book.drop(book.index[book.bigness == "l"], inplace=True)  # Allende
        book.drop(book.index[book.left_margin > 190], inplace=True)  # Allende
        book["from_left"] = book.left - book.left_margin

        book["pause"] = 0
        book.loc[book.from_left > 15, "pause"] = 1  # Allende
        book.loc[book.from_prev > 30, "pause"] = 2  # Allende
        book.loc[book.first_in_page & book.text.str.fullmatch(HEADER_RE), "pause"] = 2  # Allende(-ish)
        book.at[book.index[0], "pause"] = 2  # Always start with a bang
        para_tmap = book.pause > 0

        book.loc[para_tmap, "para"] = np.arange(1, para_tmap.sum() + 1)
        book.para = book.para.fillna(method="pad").astype(int)

        self.ddump(book, "pre-paras")

        paras = book.groupby("para").text.apply(" ".join).to_frame("text")
        paras.set_index(np.arange(1, len(paras) + 1), inplace=True)
        paras["pause"] = book[para_tmap].pause.shift(-1, fill_value=0).to_numpy()
        self.ddump(paras, "paras")

        print(f"Writing {self.args.output}")
        with open(self.args.output, "w", encoding="UTF-8") as fobj:
            for para, row in paras.iterrows():
                fobj.write(row.text)
                if row.pause == 2:
                    fobj.write("\n\n\n\n")
                elif row.pause == 1:
                    fobj.write("\n\n")

        if self.args.macos_voice:
            self.convert(paras, self.macos_tts)
        elif self.args.google_voice:
            self.convert(paras, self.google_tts)
        elif self.args.debug:
            print("Not creating audiobook")

    def convert(self, paras, tts):
        tosay = paras
        if self.args.first_prefix:
            self.args.first_paragraph = paras.index[paras.text.str.startswith(self.args.first_prefix)][0]
        if self.args.first_paragraph:
            tosay = tosay.loc[tosay.index >= self.args.first_paragraph]

        if self.args.last_prefix:
            self.args.last_paragraph = paras.index[paras.text.str.startswith(self.args.last_prefix)][0]
        if self.args.last_paragraph:
            tosay = tosay.loc[tosay.index <= self.args.last_paragraph]

        if self.args.max_paragraphs:
            tosay = tosay.iloc[:self.args.max_paragraphs]

        if len(tosay) < len(paras):
            print(f"TTS (paragraphs: {len(tosay)} of {len(paras)})")
        else:
            print(f"TTS (paragraphs: {len(tosay)})")
        stem = self.args.stem or self.args.output.stem
        for para, row in tosay.iterrows():
            path = self.args.output.with_name(f"{stem}-{para:04d}.mp3")
            if self.args.force or not path.is_file():
                tts(text=row.text, pause=row.pause, path=path)

    def macos_tts(self, text: str, pause: int, path: Path):
        """TTS using MacOS's `say (1)` and `sox`."""
        aiff = path.with_suffix(".aiff")
        subprocess.run(
            [
                "say",
                "-v",
                self.args.macos_voice,
                "-o",
                str(aiff),
                f"[[slnc 600]] " f"{text} " f"[[slnc {PAUSE_TO_GAP_MS[pause] - 600}]]",
            ],
            check=True,
        )
        subprocess.run(
            [
                "sox",
                str(aiff),
                str(path),
            ],
            check=True,
        )
        aiff.unlink()

    def list_google_voices(self):
        """List Google cloud voices"""
        from google.cloud import texttospeech as tts

        prefix = self.args.google_voice[:-1]
        print(f"Asking Google for voices starting with {repr(prefix)}...")
        client = tts.TextToSpeechClient()
        for voice in client.list_voices().voices:
            if any(lang.startswith(prefix) for lang in voice.language_codes):
                print(
                    voice.name,
                    voice.ssml_gender.name,
                    "".join(voice.language_codes),
                )

    def google_tts(self, text: str, pause: int, path: Path):
        """TTS using Google cloud."""
        from google.cloud import texttospeech as tts

        if "client" not in self.gstate:
            name = self.args.google_voice
            self.gstate["client"] = tts.TextToSpeechClient()
            self.gstate["voice"] = tts.VoiceSelectionParams(
                name=name,
                language_code=re.sub(r"^([a-z][a-z]-[A-Z][A-Z])", r"\1", name),
            )

        parts = [
            "<speak>",
            html.escape(text),
            "</speak>",
            f"""<break time="{PAUSE_TO_GAP_MS[pause]}ms"/>""",
        ]

        response = self.gstate["client"].synthesize_speech(
            request={
                "voice": self.gstate["voice"],
                "audio_config": tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3),
                "input": tts.SynthesisInput(ssml="".join(parts)),
            }
        )

        with open(path, "wb") as ofo:
            ofo.write(response.audio_content)

    def ddump(self, obj, name):
        if not self.args.debug:
            return
        path = self.args.output.parent / f"{THIS}-{name}.pickle"
        print(f"(debug) Writing {path}")
        with open(path, "wb") as fobj:
            pickle.dump(obj, fobj)

    @classmethod
    def most_common(cls, series) -> float:
        """An approximation"""
        return float(series.round(1).mode())


if __name__ == "__main__":
    Pdf2Utf().main()
