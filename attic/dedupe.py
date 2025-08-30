#!/usr/bin/env python3
"""Make hard links where possible."""
import argparse
import collections
import csv
import hashlib
import stat
import subprocess
import typing as t
from pathlib import Path

# TO DO: --exclude


class File:
    """A found file."""

    def __init__(self, root: Path, path: Path) -> None:
        self.root = root
        self.path = path
        self.info = path.lstat()

    def __repr__(self) -> str:
        return str(self.path.relative_to(self.root))

    def is_file(self) -> bool:
        """Return True iff this is a regular file."""
        return stat.S_ISREG(self.info.st_mode)

    @property
    def inode(self) -> int:
        """Inode number."""
        return self.info.st_ino

    @property
    def size(self) -> int:
        """File size."""
        return self.info.st_size

    def hash(self) -> str:
        """Read and hash a file."""
        with self.path.open("rb") as fobj:
            return hashlib.sha256(fobj.read()).hexdigest()

    def hardlink_to(self, target: t.Self) -> None:
        """Make this path a hard link to the same file as `target`."""
        print(self, "->", target)
        self.path.unlink()
        self.path.hardlink_to(target.path)


class Dedupe:
    """Make hard links where possible."""

    def run(self) -> None:
        """Dedupe."""
        parser = argparse.ArgumentParser()
        parser.add_argument("root", type=Path, default=Path.cwd())
        parser.add_argument("-e", "--exclude", type=Path, nargs="+")
        parser.add_argument("-s", "--min-size", type=int, default=1024 * 1024)
        parser.add_argument("-y", "--yes", action="store_true")
        parser.add_argument("-c", "--csv", type=Path, default="dedupe.csv")
        parser.add_argument("-C", "--open-csv", action="store_true")
        args = parser.parse_args()

        inodes: dict[int, list[File]] = collections.defaultdict(list)
        sizes: dict[int, set[int]] = collections.defaultdict(set)

        for path in args.root.rglob("*"):
            file = File(args.root, path)
            if file.is_file() and file.size >= args.min_size:
                inodes[file.inode].append(file)
                sizes[file.size].add(file.inode)

        total_save = 0
        rows: list[list[int | File]] = []
        to_merge: list[list[File]] = []
        for size, size_inodes in sizes.items():
            if len(size_inodes) == 1:
                continue  # Only one file of this size
            hashes = {inodes[inode][0].hash() for inode in size_inodes}
            if len(hashes) > 1:
                continue  # Not all the same (TO DO: maybe subsets)
            files = [
                file
                for inode in size_inodes
                for file in inodes[inode]
            ]
            to_merge.append(files)
            print(f"[{len(to_merge)}]", f"({size:,} B)", files)
            count = len(files)
            save = size * (count - 1)
            total_save += save
            rows.append([count, size, save, *files])

        if not to_merge:
            return
        print(f"Hard links would save {total_save:,} bytes")

        with Path(args.csv).open("w") as csvfo:
            csvw = csv.writer(csvfo)
            csvw.writerow(["count", "size", "save"])
            for row in rows:
                csvw.writerow(map(str, row))

        print("See also", args.csv)
        if args.open_csv:
            subprocess.run(["/usr/bin/open", str(args.csv)], check=False)
        if not args.yes:
            input("Press Return to hard link...")

        for files in to_merge:
            for file in files[1:]:
                file.hardlink_to(files[0])


if __name__ == "__main__":
    Dedupe().run()
