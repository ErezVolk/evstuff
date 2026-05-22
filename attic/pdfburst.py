#!/usr/bin/env -S uv run --script
"""Split PDF into separate pages."""
import argparse
from pathlib import Path

import pymupdf  # ty: ignore[unresolved-import]


def main() -> None:
    """Split PDF into separate pages."""
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("prefix", type=Path, nargs="?")
    args = parser.parse_args()

    prefix = args.prefix or args.input.with_suffix("")

    idoc = pymupdf.Document(args.input)
    for n in range(len(idoc)):
        ofn = prefix.with_name(f"{prefix.name}-{n + 1:02d}.pdf")
        with pymupdf.Document() as odoc:
            odoc.insert_pdf(idoc, from_page=n, to_page=n)
            odoc.save(ofn)


if __name__ == "__main__":
    main()

# /// script
# dependencies = ["pymupdf"]
# ///
