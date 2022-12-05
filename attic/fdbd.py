#!/usr/bin/env python3
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
import re


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "-r", "--root", type=Path, default=Path.home() / "Dropbox" / "Mohaliver"
    )
    args = parser.parse_args()

    src_dst = {}
    for path in args.root.glob("**/?*.*"):
        if not path.is_file():
            continue
        stem = path.stem

        if (match := re.match(r"(\d\d\d\d-\d\d-\d\d) \1(.*)", stem)):
            src_dst[path] = path.with_stem("".join(match.groups()))
            continue
        elif re.match(r"\d\d\d\d-\d\d-\d\d", stem):
            continue
        elif (match := re.search(r"(202[23])[-_ ]?(\d\d)[-_ ]?(\d\d)", stem)):
            (yyyy, mm, dd) = match.groups()
        elif (match := re.search(r"(\d\d)[-_ ]?(\d\d)[-_ ]?(202[23])", stem)):
            (dd, mm, yyyy) = match.groups()
        else:
            mdt = datetime.fromtimestamp(path.stat().st_mtime)
            (yyyy, mm, dd) = (mdt.strftime(fmt) for fmt in ["%Y", "%m", "%d"])

        src_dst[path] = path.with_stem(f"{yyyy}-{mm}-{dd} {path.stem}")

    if src_dst:
        for src, dst in src_dst.items():
            print(src, "->", dst)

        input(f"Press Return to rename {len(src_dst)} file(s)...")
        for src, dst in src_dst.items():
            src.rename(dst)
    else:
        print("Nothing to do!")


if __name__ == "__main__":
    main()
