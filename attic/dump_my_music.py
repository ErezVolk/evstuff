#!/usr/bin/env python3
"""Export Apple Music library to CSV on macOS."""
import argparse
import csv
import dataclasses as dcl
import logging
import subprocess
import time
from pathlib import Path

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_COUNT = r"""tell application "Music" to count tracks of library playlist 1"""

SCRIPT_LIST = r"""
tell application "Music"
    repeat with t in every track of library playlist 1
        try
            set tArtist to artist of t
        on error
            set tArtist to "N/A"
        end try

        try
            set tAlbum to album of t
        on error
            set tAlbum to "N/A"
        end try

        try
            set tYear to year of t
        on error
            set tYear to "N/A"
        end try

        try
            set tMillis to 1000 * duration of t as integer
        on error
            set tMillis to 0
        end try

        log (tArtist & tab & tAlbum & tab & tYear & tab & tMillis)
    end repeat
end tell
"""


@dcl.dataclass
class Album:
    """An album."""

    artist: str
    title: str
    year: str
    millis: int
    tracks: int = 1

    def same(self, artist: str, title: str) -> bool:
        """Check for sameness."""
        return (self.artist, self.title) == (artist, title)

    @staticmethod
    def header() -> list[str]:
        """Header row for CSV."""
        return [
            "Artist",
            "Title",
            "Year",
            "Tracks",
            "Seconds",
        ]

    def row(self) -> list[str]:
        """Row for CSV."""
        return [
            self.artist,
            self.title,
            self.year,
            str(self.tracks),
            str(self.millis // 1000),
        ]


@dcl.dataclass
class Args:
    """Command-line arguments."""

    output: Path
    pulse: int


class DumpMyMusic:
    """Export Apple Music library to CSV on macOS."""

    args: Args
    curr: Album | None = None
    total_tracks: int = 0
    seen_tracks: int = 0
    seen_albums: int = 0
    seen_millis: int = 0
    heartbeat: float = 0.0

    def main(self) -> None:
        """Export Apple Music library to CSV on macOS."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            default="music.csv",
            help="CSV file",
        )
        parser.add_argument(
            "--pulse",
            type=int,
            metavar="SECONDS",
            default=60,
            help="progress update interval",
        )
        self.args = Args(**vars(parser.parse_args()))

        logger.info("Reading Apple Music library...")

        count_proc = subprocess.run(
            ["/usr/bin/osascript", "-e", SCRIPT_COUNT],
            capture_output=True,
            check=True,
            text=True,
        )
        self.total_tracks = int(count_proc.stdout)
        logger.info("Total tracks: %d", self.total_tracks)

        list_proc = subprocess.Popen(
            ["/usr/bin/osascript", "-e", SCRIPT_LIST],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if list_proc.stdout is None:
            logger.error("Error communicating with Apple Music:")
            return

        self.heartbeat = time.monotonic()
        with self.args.output.open("w", newline="") as fobj:
            self.csvw = csv.writer(fobj)
            self.csvw.writerow(Album.header())

            for line in list_proc.stdout:
                self._handle(line)
            self._ship()

        code = list_proc.wait()
        if code != 0:
            logger.error("Error communicating with Apple Music:")
            return

    def _handle(self, line: str) -> None:
        try:
            artist, title, year, smillis = line.strip().split("\t")
        except ValueError:
            logger.exception("Weird line %r", line)
            return

        self.seen_tracks += 1
        self.seen_millis += (millis := int(smillis))
        if self.curr is None or not self.curr.same(artist, title):
            self.seen_albums += 1
            self._ship()
            self.curr = Album(artist, title, year, millis)
        else:
            self.curr.millis += millis
            self.curr.tracks += 1
        now = time.monotonic()
        if (now - self.heartbeat) >= self.args.pulse:
            logger.info(
                "Working: %d track(s) (%d%%), %d album(s), %s",
                self.seen_tracks,
                (100 * self.seen_tracks) // self.total_tracks,
                self.seen_albums,
                self._hhmmss(),
            )
            self.heartbeat = now

    def _ship(self) -> None:
        if self.curr is not None:
            self.csvw.writerow(self.curr.row())

    def _hhmmss(self) -> str:
        ss = self.seen_millis // 1000
        mm, ss = divmod(ss, 60)
        hh, mm = divmod(mm, 60)
        return f"{hh:,}h {mm:02d}m {ss:02d}s"


if __name__ == "__main__":
    DumpMyMusic().main()
