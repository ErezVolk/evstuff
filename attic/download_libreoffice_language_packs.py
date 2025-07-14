#!/usr/bin/env python3
"""Download LibreOffice language packs."""
import argparse
import random
import subprocess
from pathlib import Path


def download_libreoffice_language_packs() -> None:
    """Download LibreOffice language packs."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="LibreOffice version")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path.home() / "Downloads" / "libreoffice-language-packs",
        help="Base directory for outputs.",
    )
    parser.add_argument(
        "-l",
        "--langs",
        type=str,
        nargs="+",
        default=["de", "es", "fr", "it", "ja", "pt-BR", "ca"],
        help="Language codes",
    )
    parser.add_argument(
        "--tool",
        type=str,
        default="/usr/local/bin/aria2c",
        help="Downloader",
    )
    args = parser.parse_args()

    if not args.version:
        cask = Path("/usr/local/Caskroom/libreoffice")
        args.version = max(
            (path.name for path in cask.glob("*.*.*")),
            key=parse_version,
        )

    output = args.output / args.version
    output.mkdir(exist_ok=True, parents=True)

    server = (
        f"https://download.documentfoundation.org/libreoffice/stable/"
        f"{args.version}/mac/aarch64"
    )
    packs = [
        f"LibreOffice_{args.version}_MacOS_aarch64_langpack_{lang}.dmg"
        for lang in args.langs
    ]
    random.shuffle(packs)
    for pack in packs:
        subprocess.run([args.tool, f"{server}/{pack}"], cwd=output, check=True)
    subprocess.run(["/usr/bin/open", *packs], cwd=output, check=True)


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a version string."""
    v1, v2, v3 = version.split(".")
    return (int(v1), int(v2), int(v3))


if __name__ == "__main__":
    download_libreoffice_language_packs()
