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


PAUSE_TO_GAP_MS = {2: 3000, 1: 1000}


def main():
    try:
        only_pdf_here, = Path.cwd().glob("*.pdf")
        input_kwargs = {"default": only_pdf_here}
    except ValueError:
        input_kwargs = {}

    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, **input_kwargs)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("-d", "--debug", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--macos-voice")
    group.add_argument("-g", "--google-voice")
    parser.add_argument("-s", "--stem")
    parser.add_argument("-f", "--first", type=int)
    parser.add_argument("-l", "--last", type=int)
    args = parser.parse_args()

    if not args.output:
        args.output = args.input.with_suffix(".utf8")

    if args.google_voice and args.google_voice.endswith("?"):
        list_google_voices(args.google_voice[:-1])
        return

    print(f"Reading {args.input}")
    doc = fitz.Document(args.input)
    book = pd.DataFrame([
        {
            "page_label": page.get_label() or str(page_number),
            "page_number": page_number,
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

    book["odd"] = (book.page_number % 2) == 1
    book["height"] = (book.bottom - book.top).map(
        lambda h: "s" if h < 13 else "l" if h > 15 else "n"
    )
    for height in book.height.unique():
        tmap = book.height == height
        book.loc[tmap, "left_margin"] = book[tmap].groupby(
            "page_number"
        ).left.transform("min")

    if args.debug:
        write_pickle(book, args.output.with_name("raw.pickle"))

    # Merge drop caps (Allende)
    drop_cap_tmap = (book.height == "l") & (book.text.str.len() == 1)
    for loc in book.index[drop_cap_tmap]:
        drop = book.loc[loc]
        line = book.loc[loc + 1]
        book.loc[loc + 1, "text"] = f"{drop.text}{line.text}"
        book.loc[
            (
                book.page_number == drop.page_number
            ) & (
                book.top.between(drop.top, drop.bottom)
            ),
            "left"
        ] = line.left_margin
    book.drop(book.index[drop_cap_tmap], inplace=True)

    # Remove empty lines
    book.drop(book.index[book.text == ""], inplace=True)

    # Remove line numbers (TODO: risky, insufficient)
    book.drop(book.index[book.text == book.page_label], inplace=True)

    # Allende-specific
    book.drop(book.index[book.text.str.contains("\n")], inplace=True)
    book.drop(book.index[book.height == "l"], inplace=True)

    book["from_prev"] = book.groupby("page_number").bottom.diff()

    # Dehyphenate some more
    while True:
        curr_tmap = book.text.str[-1].isin(["\xad", "\u20a0", "\u2011"])
        if curr_tmap.sum() == 0:
            break
        next_tmap = curr_tmap.shift(1, fill_value=False)
        mrg = book.loc[curr_tmap].join(
            book.loc[next_tmap].set_index(book.index[curr_tmap]),
            rsuffix="_n",
        )
        mrg["text"] = mrg[["text", "text_n"]].astype(str).agg("".join, axis=1)
        same_tmap = mrg.page_number == mrg.page_number_n
        mrg.loc[same_tmap, "left"] = mrg[["left", "left_n"]].min(axis=1)
        mrg.loc[same_tmap, "top"] = mrg[["top", "top_n"]].min(axis=1)
        mrg.loc[same_tmap, "right"] = mrg[["right", "right_n"]].max(axis=1)
        mrg.loc[same_tmap, "bottom"] = mrg[["bottom", "bottom_n"]].max(axis=1)

        merge_cols = ["text", "left", "top", "right", "bottom"]
        book.loc[curr_tmap, merge_cols] = mrg[merge_cols]
        book.drop(labels=book.index[next_tmap], inplace=True)

    book.drop(book.index[book.height == "l"], inplace=True)  # Allende
    book.drop(book.index[book.left_margin > 190], inplace=True)  # Allende
    book["from_left"] = book.left - book.left_margin

    book["pause"] = 0
    book.loc[book.from_left > 15, "pause"] = 1
    book.loc[book.from_prev > 30, "pause"] = 2
    para_tmap = book.pause > 0

    book.loc[para_tmap, "para"] = np.arange(1, para_tmap.sum() + 1)
    book.para = book.para.fillna(method="pad").astype(int)

    paras = book.groupby("para").text.apply(" ".join).to_frame("text")
    paras["pause"] = book[para_tmap].pause.shift(-1, fill_value=0).to_numpy()
    if args.debug:
        write_pickle(book, args.output.with_name("paras.pickle"))

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
        tts = partial(macos_tts, voice=args.voice)
    elif args.google_voice:
        name = args.google_voice
        tts = partial(google_tts, name=name)

    if tts is not None:
        print(f"Generating audio (number of paragraphs: {len(paras)})")
        stem = args.stem or args.output.stem
        for para, row in paras.iterrows():
            if args.first and para < args.first:
                continue
            if args.last and para > args.last:
                break
            tts(
                text=row.text,
                pause=row.pause,
                path=args.output.with_name(f"{stem}-{para:04d}.mp3"),
            )


def macos_tts(voice: str, text: str, pause: int, path: Path):
    """TTS using MacOS's `say (1)` and `sox`."""
    aiff = path.with_suffix(".aiff")
    subprocess.run([
        "say",
        "-v", voice,
        "-o", str(aiff),
        f"[[slnc 600]] "
        f"{text} "
        f"[[slnc {PAUSE_TO_GAP_MS[pause] - 600}]]",
    ], check=True)
    subprocess.run([
        "sox",
        str(aiff),
        str(path),
    ], check=True)
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
    parts.extend([
        "<speak>",
        html.escape(text),
        "</speak>",
        f"""<break time="{PAUSE_TO_GAP_MS[pause] - PRE_GAP_MS}ms"/>""",
    ])

    response = gstate["client"].synthesize_speech(request={
        "voice": gstate["voice"],
        "audio_config": tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3),
        "input": tts.SynthesisInput(ssml="".join(parts))
    })

    print(path, "...")
    with open(path, "wb") as ofo:
        ofo.write(response.audio_content)


def write_pickle(obj, path):
    with open(path, "wb") as fobj:
        pickle.dump(obj, fobj)


if __name__ == "__main__":
    main()
