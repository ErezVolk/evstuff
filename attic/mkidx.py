#!/usr/bin/env python3
"""Help extracting some semblance of index from PDF files."""
# pyright: reportMissingImports=false
# pylint: disable=import-error
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

import pymupdf  # pylint: disable=import-error

THIS = Path(__file__)


class MakeIndex:
    """Help extracting some semblance of index from PDF files."""

    def parse_args(self) -> None:
        """Parse command-line."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "inputs",
            type=Path,
            nargs="*",
        )
        parser.add_argument(
            "-o", "--output-directory", type=Path, default="indexes",
        )
        parser.add_argument(
            "-p",
            "--policy",
            choices=["always", "never", "ask"],
            default="ask",
        )
        parser.add_argument(
            "-t",
            "--top-nth",
            type=int,
        )
        parser.add_argument(
            "--force-ocr",
            action="store_true",
        )
        parser.add_argument(
            "--dpi",
            type=int,
        )
        parser.add_argument(
            "-l",
            "--lang",
            type=str,
        )
        args = parser.parse_args()
        if not args.inputs:
            args.inputs = list(Path.cwd().glob("*.pdf"))
        self.args = args

    args: argparse.Namespace

    def run(self) -> None:
        """Do it."""
        self.parse_args()
        for pdf in self.args.inputs:
            self.do_file(pdf)

    def do_file(self, pdf: Path) -> None:
        """Process one file."""
        idx = self.args.output_directory / f"{pdf.stem}.txt"
        if idx.is_file():
            if self.args.policy == "never":
                print(f"Skipping {pdf} (index exists)")
                return
            if self.args.policy == "ask":
                if input(f"Enter 'y' to redo {pdf}, Enter to skip: ") != "y":
                    print(f" > Skipping {pdf}")
                    return
        print(f"Opening {pdf} for you...")
        try:
            subprocess.run(["/usr/bin/open", str(pdf)], check=True)
        except FileNotFoundError:
            print(f" > Couldn't open {pdf}, skipping")
            return
        while True:
            rstr = input(" > Enter 'skip' or page range, e.g. '1' or '2-5': ")
            if mobj := re.fullmatch(r"(skip|\d+(-\d+)?)", rstr):
                break
        if rstr == "skip":
            text = ""
        else:
            if mobj.group(2):
                pfrom, pto = list(map(int, rstr.split("-")))
            else:
                pfrom = pto = int(rstr)

            with pymupdf.open(pdf) as doc:
                text = "\n\f\n".join(
                    self.get_text(doc[pno])
                    for pno in range(pfrom - 1, pto)
                )

        idx.parent.mkdir(parents=True, exist_ok=True)
        print(f" > Writing {idx}")
        with idx.open("w", encoding="utf-8") as fobj:
            fobj.write(text)

    def get_text(self, page: pymupdf.Page) -> str:
        """Get text from a page."""
        if not self.args.force_ocr:
            text = page.get_text()
            if text.strip():
                return text

        print(f" > Running OCR on {page}...")
        with tempfile.TemporaryDirectory() as tdir:
            tiff = f"{tdir}/page.tiff"
            kwargs = {}
            if nth := self.args.top_nth:
                full = page.rect
                kwargs["clip"] = pymupdf.Rect(
                    full.x0,
                    full.y0,
                    full.x1,
                    full.y0 + full.height / nth,
                )
            if self.args.dpi:
                kwargs["dpi"] = self.args.dpi
            pixmap = page.get_pixmap(**kwargs)
            pixmap.pil_save(tiff)
            pixmap.pil_save(f"{THIS.stem}.tiff")
            cli = ["tesseract"]
            if self.args.lang:
                cli.extend(["-l", self.args.lang])
            cli.extend([tiff, "-"])
            ocr = subprocess.run(cli, check=True, capture_output=True)
            return ocr.stdout.decode()


if __name__ == "__main__":
    MakeIndex().run()
