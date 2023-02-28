#!/usr/bin/env python3
"""Currently only geared to a specific PDF"""
import argparse
from functools import partial
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


def main():
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
    parser.add_argument("-F", "--first-paragraph", type=int, help="First audio paragraph")
    parser.add_argument("-L", "--last-paragraph", type=int, help="Last audio paragraph")
    args = parser.parse_args()

    if not args.input:
        candidates = list(Path.cwd().glob("*.pdf"))
        if len(candidates) != 1:
            parser.error("Unable to guess input file name")

        (args.input,) = candidates
        input(f"Press Enter to process {repr(args.input.name)}...")

    if not args.output:
        args.output = args.input.with_suffix(".utf8")

    if args.google_voice and args.google_voice.endswith("?"):
        list_google_voices(args.google_voice[:-1])
        return

    print(f"Reading {args.input}")
    doc = fitz.Document(args.input)
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
    book = words.groupby(["page_no", "page_label", "bottom"]).apply(lambda group: pd.Series({
        "left": group.left.min(),
        "right": group.right.max(),
        "top": group.top.max(),
        "text": " ".join(group.word),
    })).reset_index()

    book["odd"] = (book.page_no % 2) == 1
    book["height"] = book.bottom - book.top

    if args.debug:
        write_pickle(book, args.output, "raw")

    if args.first_page:
        book.drop(book.index[book.page_no < args.first_page], inplace=True)
    if args.last_page:
        book.drop(book.index[book.page_no > args.last_page], inplace=True)

    # Lose printer's marks and page numbers (not very generic)
    book.drop(book.index[book.text.str.contains(".indd")], inplace=True)
    book.drop(book.index[book.text == book.page_label], inplace=True)

    common_height = book.height - most_common(book.height)
    book["bigness"] = common_height.map(
        lambda h: "s" if h < -5 else "n" if h < 5 else "l"
    )
    for bigness in book.bigness.unique():
        tmap = book.bigness == bigness
        book.loc[tmap, "left_margin"] = (
            book[tmap].groupby("page_no").left.transform("min")
        )

    if args.debug:
        write_pickle(book, args.output, "culled")

    # Merge drop caps (Allende)
    drop_cap_tmap = (book.bigness == "l") & (book.text.str.len() == 1)
    for loc in book.index[drop_cap_tmap]:
        drop = book.loc[loc]
        line = book.loc[loc + 1]
        book.loc[loc + 1, "text"] = f"{drop.text}{line.text}"
        overlap = (
            book.query(f"page_no == {drop.page_no}")
            .query(
                f"top.between({drop.top}, {drop.bottom})",
            )
            .index
        )
        book.loc[overlap, "left"] = line.left_margin
    book.drop(book.index[drop_cap_tmap], inplace=True)

    # Remove empty lines
    book.drop(book.index[book.text == ""], inplace=True)

    # Remove line numbers (TODO: risky, insufficient)
    book.drop(book.index[book.text == book.page_label], inplace=True)

    # Allende-specific
    book.drop(book.index[book.text.str.contains("\n")], inplace=True)
    book.drop(book.index[book.bigness == "l"], inplace=True)

    book["from_prev"] = book.groupby("page_no").bottom.diff()

    common_first_bottom = most_common(book.groupby("page_no").bottom.min())
    common_last_bottom = most_common(book.groupby("page_no").bottom.max())
    book["from_first_bottom"] = book.bottom - common_first_bottom
    book["from_last_bottom"] = common_last_bottom - book.bottom

    book["first_in_page"] = first_tmap = book.from_prev.isna()
    book.loc[first_tmap, "from_prev"] = book[first_tmap].bottom - common_first_bottom
    if args.debug:
        write_pickle(book, args.output, "pre-merge")

    # Dehyphenate some more
    while True:
        curr_tmap = book.text.str[-1].isin(["\xad", "\u20a0", "\u2011", "-"])
        if curr_tmap.sum() == 0:
            break
        next_tmap = curr_tmap.shift(1, fill_value=False)
        mrg = book.loc[curr_tmap].join(
            book.loc[next_tmap].set_index(book.index[curr_tmap]),
            rsuffix="_n",
        )
        mrg["text_c"] = mrg.text.str[:-1]
        mrg["text"] = mrg[["text_c", "text_n"]].astype(str).agg("".join, axis=1)
        same_tmap = mrg.page_no == mrg.page_no_n
        mrg.loc[same_tmap, "left"] = mrg[["left", "left_n"]].min(axis=1)
        mrg.loc[same_tmap, "top"] = mrg[["top", "top_n"]].min(axis=1)
        mrg.loc[same_tmap, "right"] = mrg[["right", "right_n"]].max(axis=1)
        mrg.loc[same_tmap, "bottom"] = mrg[["bottom", "bottom_n"]].max(axis=1)

        merge_cols = ["text", "left", "top", "right", "bottom"]
        book.loc[curr_tmap, merge_cols] = mrg[merge_cols]
        book.drop(labels=book.index[next_tmap], inplace=True)

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

    paras = book.groupby("para").text.apply(" ".join).to_frame("text")
    paras["pause"] = book[para_tmap].pause.shift(-1, fill_value=0).to_numpy()
    if args.debug:
        write_pickle(book, args.output, "paras")

    print(f"Writing {args.output}")
    with open(args.output, "w", encoding="UTF-8") as fobj:
        for para, row in paras.iterrows():
            fobj.write(row.text)
            if row.pause == 2:
                fobj.write("\n\n\n\n")
            elif row.pause == 1:
                fobj.write("\n\n")

    tts = None
    if args.macos_voice:
        tts = partial(macos_tts, voice=args.macos_voice)
    elif args.google_voice:
        name = args.google_voice
        tts = partial(google_tts, name=name)

    if tts is not None:
        tosay = paras
        if args.first_paragraph:
            tosay = tosay.loc[tosay.index >= args.first_paragraph]
        if args.last_paragraph:
            tosay = tosay.loc[tosay.index <= args.last_paragraph]
        if len(tosay) < len(paras):
            print(f"TTS (paragraphs: {len(tosay)} of {len(paras)})")
        else:
            print(f"TTS (paragraphs: {len(tosay)})")
        stem = args.stem or args.output.stem
        for para, row in tosay.iterrows():
            tts(
                text=row.text,
                pause=row.pause,
                path=args.output.with_name(f"{stem}-{para:04d}.mp3"),
            )


def macos_tts(voice: str, text: str, pause: int, path: Path):
    """TTS using MacOS's `say (1)` and `sox`."""
    aiff = path.with_suffix(".aiff")
    subprocess.run(
        [
            "say",
            "-v",
            voice,
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


gstate = {}


def list_google_voices(prefix: str):
    """List Google cloud voices"""
    from google.cloud import texttospeech as tts

    print(f"Asking Google for voices starting with {repr(prefix)}...")
    client = tts.TextToSpeechClient()
    for voice in client.list_voices().voices:
        if any(lang.startswith(prefix) for lang in voice.language_codes):
            print(
                voice.name,
                voice.ssml_gender.name,
                "".join(voice.language_codes),
            )


def google_tts(name: str, text: str, pause: int, path: Path):
    """TTS using Google cloud."""
    from google.cloud import texttospeech as tts

    PRE_GAP_MS = 0

    if "client" not in gstate:
        gstate["client"] = tts.TextToSpeechClient()
        gstate["voice"] = tts.VoiceSelectionParams(
            name=name,
            language_code=re.sub(r"^([a-z][a-z]-[A-Z][A-Z])", r"\1", name),
        )

    parts = []
    if PRE_GAP_MS > 0:
        parts.append(f"""<break time="{PRE_GAP_MS}ms"/>""")
    parts.extend(
        [
            "<speak>",
            html.escape(text),
            "</speak>",
            f"""<break time="{PAUSE_TO_GAP_MS[pause] - PRE_GAP_MS}ms"/>""",
        ]
    )

    response = gstate["client"].synthesize_speech(
        request={
            "voice": gstate["voice"],
            "audio_config": tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3),
            "input": tts.SynthesisInput(ssml="".join(parts)),
        }
    )

    with open(path, "wb") as ofo:
        ofo.write(response.audio_content)


def write_pickle(obj, near, name):
    path = near.parent / f"{THIS}-{name}.pickle"
    print(f"(debug) Writing {path}")
    with open(path, "wb") as fobj:
        pickle.dump(obj, fobj)


def most_common(series) -> float:
    """An approximation"""
    return float(series.round(1).mode())


if __name__ == "__main__":
    main()
