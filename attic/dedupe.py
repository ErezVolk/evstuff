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

__TODO__ = """
- Proper, rsync/tar-like exclude
"""

DEFAULT_MIN_SIZE = 1024 * 1024


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", type=Path, nargs="+", default=Path.cwd())
    parser.add_argument(
        "-s",
        "--min-size",
        type=int,
        default=DEFAULT_MIN_SIZE,
        help=f"Ignore files smaller than this [{kbmbgb(DEFAULT_MIN_SIZE)}]",
    )
    parser.add_argument(
        "-a",
        "--archive",
        action="store_true",
        help="Consider owner, group, and mode",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not wait for permission.",
    )
    group.add_argument(
        "-Y",
        "--dont-wait",
        action="store_true",
        help="Link files as they are found.",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-c",
        "--csv",
        type=Path,
        default="dedupe.csv",
        help="Write CSV report",
    )
    group.add_argument(
        "-C",
        "--no-csv",
        action="store_true",
        help="Write CSV report",
    )

    parser.add_argument(
        "-o",
        "--open-csv",
        action="store_true",
        help="Open CSV report after running",
    )
    parser.add_argument("-g", "--include-git", action="store_true")
    parser.add_argument("-S", "--include-svn", action="store_true")
    parser.add_argument("-z", "--include-zotero", action="store_true")
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
        try:
            self.path.unlink()
            self.path.hardlink_to(target.path)
        except PermissionError as exc:
            print(exc)


class Walker:
    """Walk a tree."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.roots: list[Path] = args.roots
        self.min_size: int = args.min_size
        self.include_git: bool = args.include_git
        self.include_svn: bool = args.include_svn
        self.include_zotero: bool = args.include_zotero

    def walk(self) -> t.Iterable[File]:
        """Walk a tree."""
        for root in self.roots:
            if not root.is_dir():
                print(f"Not a directory: {root}")
            else:
                yield from self._walk(root, root)

    def _walk(self, root: Path, branch: Path) -> t.Iterable[File]:
        if self._should_skip(branch):
            return

        for path in branch.iterdir():
            info = path.lstat()
            mode = info.st_mode
            if stat.S_ISLNK(mode):
                continue
            if stat.S_ISREG(mode):
                if info.st_size >= self.min_size:
                    yield File(root, path, info)
            elif stat.S_ISDIR(mode):
                yield from self._walk(root, path)

    def _should_skip(self, path: Path) -> bool:
        """Check if we're configured to skip a directory."""
        if not self.include_git:
            if (path / ".git").is_dir():
                print(f"Skipping Git repo {path}")
                return True

        if not self.include_svn:
            if (path / ".svn").is_dir():
                print(f"Skipping Subversion {path}")
                return True

        if not self.include_zotero:
            if path.name == "storage":
                if (path.parent / "zotero.sqlite").is_file():
                    print(f"Skipping Zotero storage {path}")
                    return True

        return False


class Dedupe:
    """Make hard links where possible."""

    args: argparse.Namespace
    inode_to_files: dict[int, list[File]]
    gist_to_inodes: dict[int, set[int]]
    counts: dict[str, int]

    def run(self) -> None:
        """Dedupe."""
        self.args = parse_args()
        self.counts = collections.defaultdict(int)
        self.scan_files()

        scannees = [
            gist_inodes
            for gist_inodes in self.gist_to_inodes.values()
            if len(gist_inodes) > 1
        ]

        print(
            f"Checking out {len(scannees):,} of "
            f"{len(self.gist_to_inodes):,} gists.",
        )

        report: list[list[int | File]] = []
        to_merge: list[list[File]] = []
        for gist_inodes in scannees:
            snaps = self.snap_inodes(gist_inodes)

            for snap_heads in snaps.values():
                if (num_heads := len(snap_heads)) <= 1:
                    continue
                files = [
                    file
                    for head in snap_heads
                    for file in self.inode_to_files[head.inode]
                ]
                num_files = len(files)
                to_merge.append(files)

                size = files[0].size
                print(
                    f"[{len(to_merge)}] ({kbmbgb(size)}) "
                    f"[{num_files}/{num_heads}] "
                    f"{files}",
                )
                save = size * (num_heads - 1)
                self.counts["total_save"] += save
                report.append([num_heads, num_files, size, save, *files])

                if self.args.dont_wait:
                    self.merge(files)

        print(
            f"Files seen/peeked/read: "
            f"{self.counts['total_files']}/"
            f"{self.counts['peek']}/"
            f"{self.counts['snap']}",
        )
        if not to_merge:
            return

        print(f"Savings: {kbmbgb(self.counts['total_save'])}")

        if self.args.dont_wait:
            return

        if not self.args.yes:
            input("Press Return to hard link...")

        for files in to_merge:
            self.merge(files)

    def scan_files(self) -> None:
        """Scan all large enough files."""
        self.inode_to_files = collections.defaultdict(list)
        self.gist_to_inodes = collections.defaultdict(set)

        for file in Walker(self.args).walk():
            self.counts["total_files"] += 1
            self.inode_to_files[file.inode].append(file)
            self.gist_to_inodes[self.gist(file)].add(file.inode)

    def snap_inodes(self, inodes: set[int]) -> dict[str, list[File]]:
        """Scan candidates, split them by hash of beginning."""
        gist_heads = [self.inode_to_files[inode][0] for inode in inodes]
        peeks: dict[str, list[File]] = collections.defaultdict(list)
        for head in gist_heads:
            peeks[head.peek()].append(head)
            self.counts["peek"] += 1

        snaps: dict[str, list[File]] = collections.defaultdict(list)
        for peek_heads in peeks.values():
            if len(peek_heads) <= 1:
                continue
            for head in peek_heads:
                self.counts["snap"] += 1
                snaps[head.snap()].append(head)

        return peeks

    def merge(self, files: list[File]) -> None:
        """Actually create the hard links."""
        pivot = max(files, key=lambda file: file.info.st_mtime)
        for file in files:
            if file is not pivot:
                file.hardlink_to(pivot)

    def gist(self, file: File) -> int:
        """Get the gist of the file."""
        if not self.args.archive:
            return file.size
        info = file.info
        gist = (
            info.st_size,
            info.st_mode,
            info.st_uid,
            info.st_gid,
        )
        return hash(gist)

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


TENNISH = 9.995
HUNDREDISH = 99.95
THOUSANDISH = 999.5


def kbmbgb(num: float) -> str:
    """Format a number as "932K", etc."""
    prefixes = ["", "KiB", "MiB", "GiB", "TiB"]
    for prefix in prefixes:
        if abs(num) < TENNISH:
            return f"{num:,.2f} {prefix}"
        if abs(num) < HUNDREDISH:
            return f"{num:,.1f} {prefix}"
        if abs(num) < THOUSANDISH:
            return f"{num:,.0f} {prefix}"
        num = num / 1024
    return f"{num:,.1f} {prefixes[-1]}"


if __name__ == "__main__":
    Dedupe().run()
