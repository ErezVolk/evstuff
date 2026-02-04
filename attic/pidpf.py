#!/usr/bin/env python3
"""Pack InDesign published folder."""
import argparse  # noqa: I001
import datetime
from pathlib import Path
import shutil
import string
import tempfile
import typing as t
import zipfile


class PackInDesignPublishedFolder:
    """Pack InDesign published folder."""

    args: argparse.Namespace

    def parse_args(self) -> None:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-D", "--no-delete",
            action="store_true",
            help="Do NOT remove packed folder",
        )
        self.args = parser.parse_args()

    def main(self) -> None:
        """Pack InDesign published folder."""
        self.parse_args()
        count = 0

        for folder in Path.cwd().iterdir():
            count += self.consider_folder(folder)

        if count > 0:
            print(f"Converted {count} folder(s).")
        else:
            print("Could not convert any folder.")

    def consider_folder(self, folder: Path) -> int:
        """Pack folder if it is indeed an InDesign thingy."""
        if not folder.is_dir():
            return 0  # False alarm

        if not (folder / "Document fonts").is_dir():
            return 0  # Not packed

        the_pdf: Path | None = None
        for a_pdf in folder.glob("*.pdf", case_sensitive=False):
            if not a_pdf.is_file():
                continue  # False alarm
            if the_pdf is not None:
                return 0  # Multiple PDFs, not packed
            the_pdf = a_pdf

        if the_pdf is None:
            return 0  # No PDF

        pdf_stem = the_pdf.stem
        if not folder.name.startswith(pdf_stem):
            return 0  # Too weird

        return self.do_folder(folder, the_pdf)

    def do_folder(self, id_folder: Path, id_pdf: Path) -> int:
        """Found a packed id_folder, ship it."""
        today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
        stump = f"{id_pdf.stem}-{today}"
        for suffix in self.suffixes():
            stem = f"{stump}{suffix}"
            ship_pdf = Path(f"{stem}.pdf")
            ship_zip = Path(f"{stem}.zip")
            if not ship_pdf.exists() and not ship_zip.exists():
                break
        else:
            print(f"Giving up on {stump}")
            return 0

        print(f"{id_folder}/ -> {ship_zip}")
        with tempfile.TemporaryDirectory() as tdir:
            tzip = Path(tdir) / "ship.zip"
            with zipfile.ZipFile(tzip, "w", zipfile.ZIP_DEFLATED) as zfo:
                for path in id_folder.rglob("*"):
                    if not path.is_file():
                        continue
                    relname = path.relative_to(id_folder)
                    zfo.write(path, f"{stem}/{relname}")
            tzip.move(ship_zip)

        print(f"{id_pdf} -> {ship_pdf}")
        id_pdf.copy(ship_pdf)

        if not self.args.no_delete:
            print(f"Remove {id_folder}")
            shutil.rmtree(id_folder)

        return 1

    def suffixes(self) -> t.Iterable[str]:
        """Generate suffixes for a stem."""
        yield ""
        yield from string.ascii_lowercase


if __name__ == "__main__":
    PackInDesignPublishedFolder().main()
