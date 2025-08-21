#!/usr/bin/env python3
"""Extract PDF pages with annotations."""
import argparse
from pathlib import Path

import pymupdf  # type: ignore; pip install pymupdf

HALF = pymupdf.Matrix(.5, .5)


def extract_annotations() -> None:
    """Extract PDF pages with annotations."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Input PDF file",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=Path,
        help="Extract changed pages",
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
        input(f"Press Enter to process {args.input.name!r}...")

    if not args.output:
        args.output = args.input.with_stem(
            f"{args.input.stem}-annotated",
        )

    print(f"Reading {args.input}")
    indoc = pymupdf.Document(args.input)
    modoc = None
    if args.model is not None:
        print(f"Reading model {args.model}")
        modoc = pymupdf.Document(args.model)
        if len(indoc) != len(modoc):
            print(
                f"Cannot use {args.model} as the model, as the number of pages"
                f" is {len(modoc)} != {len(indoc)}",
            )
            modoc = None

    outdoc = pymupdf.Document()
    for inpage in indoc:
        if should_copy(inpage, modoc):
            outdoc.insert_pdf(
                indoc,
                from_page=inpage.number,
                to_page=inpage.number,
                final=False,
            )

    if (npages := len(outdoc)) == 0:
        print("No annotations found, doing nothing")
        return
    print(f"Writing {args.output} (n = {npages})")
    outdoc.ez_save(args.output)


def should_copy(inpage: pymupdf.Page, modoc: pymupdf.Document) -> bool:
    """Check whether a page should be copied."""
    if inpage.annot_names():
        return True
    if modoc is None:
        return False
    mopage = modoc[inpage.number]
    inpix = inpage.get_pixmap(matrix=HALF)
    mopix = mopage.get_pixmap(matrix=HALF)
    return inpix.digest != mopix.digest


if __name__ == "__main__":
    extract_annotations()
