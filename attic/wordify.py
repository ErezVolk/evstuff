#!/usr/bin/env python3
"""Find words with vowels in a docx, compare to dict"""
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path
import re

from wp2tt.docx import DocxInput

_NIQQ = "\u05B0-\u05BC\u05C1\u05C2"
_ALPH = "\u05D0-\u05EA"
_OTHR = "\u05F3"
_HEBR = f"{_NIQQ}{_ALPH}{_OTHR}"


def main():
    """Find words with vowels in a docx, compare to dict"""
    parser = ArgumentParser()
    parser.add_argument("-i", "--input", metavar="DOCX_FILE", type=Path)
    parser.add_argument(
        "-s",
        "--styles",
        metavar="WILDCARD",
        nargs="+",
    )
    parser.add_argument(
        "--list-styles",
        action="store_true",
        help="List paragraph styles in document and exit",
    )
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    if args.input is None:
        (args.input,) = Path.cwd().glob("moadon-*.docx")
        print(f"Input: {args.input}")

    if args.output is None:
        args.output = args.input.with_suffix(".words")
        print(f"Output: {args.output}")

    doc = DocxInput(args.input)
    styles = {
        style["wpid"]: style["internal_name"]
        for style in doc.styles_defined()
        if style["realm"] == "paragraph"
    }
    if args.list_styles:
        for wpid, name in styles.items():
            print(f"{wpid}\t{name}")
        return

    if args.styles:
        wpids = {
            wpid
            for wpid, name in styles.items()
            if any(name.startswith(prefix) for prefix in args.styles)
        }
        if not wpids:
            parser.error("No matching styles found")
    else:
        wpids = None

    with open("hebrew.words", encoding="utf-8") as fobj:
        hebrew = {line.split("\t")[0] for line in fobj if "\t" in line}

    wrd2niqs = defaultdict(set)
    missing = set()
    for para in doc.paragraphs():
        if wpids:
            if para.style_wpid() not in wpids:
                continue

        text = "".join(t for t in para.text())
        text = text.replace("\u05BF", " ")
        text = re.sub(f"[^{_NIQQ}{_ALPH}{_OTHR} ]", "", text)
        for niq in text.split(" "):
            wrd = re.sub(f"[{_NIQQ}]", "", niq)
            if wrd == niq:
                continue

            if niq not in hebrew and niq.removeprefix("וְ") not in hebrew:
                missing.add(niq)

            wrd2niqs[wrd].add(niq)

            # wrd2niqs[re.sub("[א]", "", wrd)].add(
            #     re.sub("([א][\u05B0-\u05BC]*)", r"(\1)", niq)
            # )

            for prefix in ["הַ", "וּ", "וְ", "שֶׁ"]:
                if niq.startswith(prefix):
                    stem = niq[len(prefix) :]
                    nniq = f"({prefix}){stem}"
                    wrd2niqs[wrd[1:]].add(nniq)

    with open(args.output, "w", encoding="utf-8") as fobj:
        badniqs = {
            wrd: niqs
            for wrd, niqs in wrd2niqs.items()
            if len(niqs) > 1
        }
        for wrd, niqs in sorted(badniqs.items()):
            fobj.write(f"{wrd}\t{' '.join(sorted(niqs))}\n")
        print(f"Number of words with more than one variant: {len(badniqs)}")
        for niq in sorted(missing):
            fobj.write(f"{niq}\n")
        print(f"Number of missing words: {len(missing)}")


if __name__ == "__main__":
    main()
