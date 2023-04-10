#!/usr/bin/env python3
"""Extract PDF pages with annotations"""
import argparse
from pathlib import Path

import fitz


def extract_annotations():
    """Extract PDF pages with annotations"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Input PDF file",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output PDF file",
    )
    args = parser.parse_args()

    if not args.input:
        candidates = [
            path
            for path in Path.cwd().glob("*.pdf")
            if not path.stem.endswith("-annotated")
        ]
        if len(candidates) != 1:
            parser.error("Unable to guess input file name")
        input(f"Press Enter to process {repr(args.input.name)}...")

    if not args.output:
        args.output = args.input.with_stem(
            f"{args.input.stem}-annotated"
        )

    print(f"Reading {args.input}")
    indoc = fitz.Document(args.input)
    outdoc = fitz.Document()
    for page in indoc:
        if page.annot_names():
            outdoc.insert_pdf(indoc, page.number, page.number, final=False)
    if (npages := len(outdoc)) == 0:
        print("No annotations found, doing nothing")
        return
    print(f"Writing {args.output} (n = {npages})")
    outdoc.ez_save(args.output)


if __name__ == "__main__":
    extract_annotations()
