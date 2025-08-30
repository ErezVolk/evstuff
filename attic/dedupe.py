#!/usr/bin/env python3
"""Make hard links where possible."""
import argparse
import collections
import csv
import hashlib
import os
import stat
import subprocess
import typing as t
from pathlib import Path

# TO DO: --exclude


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, default=Path.cwd())
    parser.add_argument("-e", "--exclude", type=Path, nargs="+")
    parser.add_argument("-s", "--min-size", type=int, default=1024 * 1024)
    parser.add_argument("-y", "--yes", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--csv", type=Path, default="dedupe.csv")
    group.add_argument("-C", "--no-csv", action="store_true")

    parser.add_argument("-o", "--open-csv", action="store_true")
    parser.add_argument("-g", "--include-git", action="store_true")
    return parser.parse_args()


class File:
    """A found file."""

    def __init__(self, root: Path, path: Path, info: os.stat_result) -> None:
        self.root = root
        self.path = path
        self.info = info

    def __repr__(self) -> str:
        return str(self.path.relative_to(self.root))

    @property
    def inode(self) -> int:
        """Inode number."""
        return self.info.st_ino

    @property
    def size(self) -> int:
        """File size."""
        return self.info.st_size

    def peek(self) -> str:
        """Read and hash part a file."""
        return self._hash(1024 * 1024)

    def snap(self) -> str:
        """Read and hash a file."""
        return self._hash()

    def _hash(self, size: int = -1) -> str:
        """Read and hash beginning a file."""
        with self.path.open("rb") as fobj:
            return hashlib.sha256(fobj.read(size)).hexdigest()

    def hardlink_to(self, target: t.Self) -> None:
        """Make this path a hard link to the same file as `target`."""
        print(self, "->", target)
        self.path.unlink()
        self.path.hardlink_to(target.path)


class Walker:
    """Walk a tree."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.root: Path = args.root
        self.min_size: int = args.min_size
        self.include_git: bool = args.include_git

    def walk(self) -> t.Iterable[File]:
        """Walk a tree."""
        yield from self._walk(self.root)

    def _walk(self, branch: Path) -> t.Iterable[File]:
        if not self.include_git:
            if (branch / ".git").is_dir():
                print(f"Skipping Git repo {branch}")
                return

        for path in branch.iterdir():
            info = path.lstat()
            mode = info.st_mode
            if stat.S_ISLNK(mode):
                continue
            if stat.S_ISREG(mode):
                if info.st_size >= self.min_size:
                    yield File(self.root, path, info)
            elif stat.S_ISDIR(mode):
                yield from self._walk(path)


class Dedupe:
    """Make hard links where possible."""

    args: argparse.Namespace

    def run(self) -> None:
        """Dedupe."""
        self.args = parse_args()

        inodes: dict[int, list[File]] = collections.defaultdict(list)
        sizes: dict[int, set[int]] = collections.defaultdict(set)

        # Scan all large enough files
        for file in Walker(self.args).walk():
            inodes[file.inode].append(file)
            sizes[file.size].add(file.inode)

        total_save = 0
        report: list[list[int | File]] = []
        to_merge: list[list[File]] = []
        for size, size_inodes in sizes.items():
            if len(size_inodes) == 1:
                continue  # Only one file of this size

            size_heads = [inodes[inode][0] for inode in size_inodes]
            peeks: dict[str, list[File]] = collections.defaultdict(list)
            for head in size_heads:
                peeks[head.peek()].append(head)

            snaps: dict[str, list[File]] = collections.defaultdict(list)
            for peek_heads in peeks.values():
                if len(peek_heads) <= 1:
                    continue
                for head in peek_heads:
                    snaps[head.snap()].append(head)

            for snap_heads in snaps.values():
                if (num_heads := len(snap_heads)) <= 1:
                    continue
                files = [
                    file
                    for head in snap_heads
                    for file in inodes[head.inode]
                ]
                num_files = len(files)
                to_merge.append(files)

                print(
                    f"[{len(to_merge)}] ({size:,} B) "
                    f"[{num_files}/{num_heads}] "
                    f"{files}",
                )
                save = size * (num_heads - 1)
                total_save += save
                report.append([num_heads, num_files, size, save, *files])

        if not to_merge:
            return

        print(f"Hard links would save {total_save:,} bytes")

        if not self.args.yes:
            input("Press Return to hard link...")

        for files in to_merge:
            for file in files[1:]:
                file.hardlink_to(files[0])

    def do_csv(self, report: list[list[int | File]]) -> None:
        """Write and open the CSV report."""
        if self.args.no_csv:
            return

        with Path(self.args.csv).open("w") as csvfo:
            csvw = csv.writer(csvfo)
            csvw.writerow(["inodes", "files", "size", "save"])
            for row in report:
                csvw.writerow(map(str, row))

        print("See also", self.args.csv)
        if self.args.open_csv:
            subprocess.run(["/usr/bin/open", str(self.args.csv)], check=False)


if __name__ == "__main__":
    Dedupe().run()
