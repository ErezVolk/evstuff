#!/usr/bin/env python3
"""Simple 2-up for PDFs."""
# pyright: reportMissingImports=false
# pylint: disable=import-error

import argparse
from pathlib import Path

import pymupdf


class Pdf2Up:
    """Simple 2-up for PDFs."""

    def parse_args(self) -> None:
        """Parse command line arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument("input", type=Path)
        parser.add_argument("output", type=Path, nargs="?")
        parser.add_argument("-f", "--first", type=int)
        parser.add_argument("-l", "--last", type=int)
        self.args = args = parser.parse_args()
        if not args.output:
            args.output = args.input.with_stem(f"{args.input.stem}-2up")

    args: argparse.Namespace

    def run(self) -> None:
        """Run."""
        self.parse_args()

        isize = self.args.input.stat().st_size
        print(f"{self.args.input} ({isize:,} B)-> {self.args.output}")
        odoc = pymupdf.Document()
        opage: pymupdf.Page | None = None
        recs: list[pymupdf.Rect] = []

        pages_kwargs = {}
        if self.args.first:
            pages_kwargs["start"] = self.args.first - 1
        if self.args.last:
            pages_kwargs["stop"] = self.args.last

        with pymupdf.Document(self.args.input) as idoc:
            for ipage in idoc.pages(**pages_kwargs):
                subidx = ipage.number % 2
                if subidx == 0:
                    oheight = ipage.rect.width
                    owidth = ipage.rect.height
                    opage = odoc.new_page(-1, width=owidth, height=oheight)
                    recs = [
                        pymupdf.Rect(0, 0, owidth / 2, oheight),
                        pymupdf.Rect(owidth / 2, 0, owidth, oheight),
                    ]
                assert opage is not None
                opage.show_pdf_page(
                    recs[subidx],
                    idoc,
                    ipage.number,
                )
        odoc.ez_save(self.args.output)
        osize = self.args.output.stat().st_size
        print(f" -> {osize:,} B ({osize * 100 // isize}%)")


if __name__ == "__main__":
    Pdf2Up().run()
