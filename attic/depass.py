#!/usr/bin/env python3
"""Remove password from PDF."""
import getpass
import sys
from pathlib import Path

import pymupdf


def depass() -> None:
    """Remove password from one or more PDFs."""
    for name in sys.argv[1:]:
        depass_file(Path(name))


def depass_file(path: Path) -> None:
    """Remove password from one PDFs."""
    doc = pymupdf.open(path)
    password = getpass.getpass(f"Enter password for {path}")
    doc.authenticate(password)
    output = path.with_stem(f"{path.stem}-open")
    print(f"Writing {output}")
    doc.save(output)


if __name__ == "__main__":
    depass()
