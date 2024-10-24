#!/usr/bin/env python3
"""Crop PDF even more."""
import argparse
from pathlib import Path

import pymupdf


class CropMore:
    """Crop PDF even more."""

    parser: argparse.ArgumentParser
    args: argparse.Namespace
    cropping: bool

    def parse_args(self) -> None:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument("input", type=Path, nargs="?", help="Input PDF")
        parser.add_argument("output", type=Path, nargs="?", help="Output PDF")
        parser.add_argument("-f", "--first-page", type=int, help="First page")
        parser.add_argument("-l", "--last-page", type=int, help="Last page")
        parser.add_argument(
            "-M",
            "--media",
            action="store_true",
            help="Use mediabox as basis for cropping",
        )
        parser.add_argument(
            "-A",
            "--all",
            type=int,
            default=0,
            help="Crop on all sides (--top etc. override this)",
        )
        parser.add_argument("-T", "--top", type=int, help="Top crop")
        parser.add_argument("-B", "--bottom", type=int, help="Bottom crop")
        parser.add_argument("-L", "--left", type=int, help="Left crop")
        parser.add_argument("-R", "--right", type=int, help="Right crop")
        parser.add_argument(
            "-p", "--pixmap", action="store_true", help="Convert to graphics",
        )
        parser.add_argument(
            "-D", "--dpi", type=int, default=600, help="Used when --pixmap",
        )

        args = parser.parse_args()

        for item in ["top", "bottom", "left", "right"]:
            if getattr(args, item) is None:
                setattr(args, item, args.all)

        self.cropping = any([args.top, args.bottom, args.left, args.right, args.media])
        if not any([args.first_page, args.last_page, self.cropping]):
            parser.error("You must specify something to trim")

        if args.input is None:
            paths = [
                path
                for path in Path.cwd().glob("*.pdf")
                if not path.stem.endswith("-cropped")
            ]
            if len(paths) != 1:
                parser.error("Please specify input PDF")
            args.input = paths[0]
            input(f"Press Enter to process `{args.input}'...")

        if args.output is None:
            args.output = args.input.with_stem(args.input.stem + "-cropped")

        self.parser = parser
        self.args = args

    def main(self) -> None:
        """Do it."""
        self.parse_args()

        print(f"`{self.args.input}' -> `{self.args.output}'")
        idoc = pymupdf.Document(self.args.input)
        odoc = pymupdf.Document()

        odoc.insert_pdf(
            idoc,
            from_page=self.args.first_page - 1 if self.args.first_page else -1,
            to_page=self.args.last_page - 1 if self.args.last_page else -1,
        )

        if self.cropping:
            for page in odoc:
                box = page.mediabox if self.args.media else page.cropbox
                crop = pymupdf.Rect(
                    box.x0 + self.args.left,
                    box.y0 + self.args.top,
                    box.x1 - self.args.right,
                    box.y1 - self.args.bottom,
                )
                page.set_cropbox(crop)

        if self.args.pixmap:
            tdoc = odoc
            odoc = pymupdf.Document()
            for tpage in tdoc:
                timg = tpage.get_pixmap(dpi=self.args.dpi)
                opage = odoc.new_page(
                    width=tpage.cropbox.width,
                    height=tpage.cropbox.height,
                )
                opage.insert_image(
                    opage.cropbox,
                    pixmap=timg,
                )

        odoc.ez_save(self.args.output)


if __name__ == "__main__":
    CropMore().main()
