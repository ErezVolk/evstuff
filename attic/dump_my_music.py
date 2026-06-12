#!/usr/bin/env python3
"""Export Apple Music library to CSV on macOS."""
import argparse
import csv
import logging
import subprocess
import time
import typing as t
from pathlib import Path

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_COUNT = r"""tell application "Music" to count tracks of library playlist 1"""

SCRIPT_LIST = r"""
on replace_chars(this_text, search_string, replacement_string)
 set AppleScript's text item delimiters to the search_string
 set the item_list to every text item of this_text
 set AppleScript's text item delimiters to the replacement_string
 set this_text to the item_list as string
 set AppleScript's text item delimiters to ""
 return this_text
end replace_chars

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
            set tTrack to name of t
        on error
            set tTrack to "N/A"
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

        set tComment to comment of t
        set tComment to replace_chars(comment, "\n", " | ")

        set tGenre to genre of t

        set tLiked to favorited of t or album favorited of t

        set tCount to played count of t

        log (¬
            tArtist & tab & ¬
            tAlbum & tab & ¬
            tTrack & tab & ¬
            tYear & tab & ¬
            tMillis & tab & ¬
            tGenre & tab & ¬
            tComment & tab & ¬
            tLiked & tab & ¬
            tCount)
    end repeat
end tell
"""


class Album(t.NamedTuple):
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


class Args(t.NamedTuple):
    """Command-line arguments."""

    output: Path
    pulse: int


class Finding(t.NamedTuple):
    """Line passed from AppleScript."""

    artist: str
    album: str
    track: str
    year: str
    millis: str
    genre: str
    comment: str
    liked: str
    count: str


class DumpMyMusic:
    """Export Apple Music library to CSV on macOS."""

    args: Args
    curr: tuple[str, str] | None = None
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
            self.csvw.writerow([
                "Artist",
                "Album",
                "Track",
                "Year",
                "Millis",
                "Genre",
                "Comment",
                "Liked",
                "Played",
            ])

            for line in list_proc.stdout:
                self._handle(line)

        code = list_proc.wait()
        if code != 0:
            logger.error("Error communicating with Apple Music:")
            return

    def _handle(self, line: str) -> None:
        try:
            finding = Finding(*line.strip().split("\t"))
        except (ValueError, TypeError):
            logger.exception("Weird line %r", line)
            return

        self.seen_tracks += 1
        self.seen_millis += int(finding.millis)
        aaid = (finding.artist, finding.album)

        if self.curr != aaid:
            self.seen_albums += 1
            self.curr = aaid
        self.csvw.writerow([
            finding.artist,
            finding.album,
            finding.track,
            finding.year,
            finding.millis,
            finding.genre,
            finding.comment,
            finding.liked,
            finding.count,
        ])

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

    def _hhmmss(self) -> str:
        ss = self.seen_millis // 1000
        mm, ss = divmod(ss, 60)
        hh, mm = divmod(mm, 60)
        return f"{hh:,}h {mm:02d}m {ss:02d}s"


if __name__ == "__main__":
    DumpMyMusic().main()
