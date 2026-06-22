#!/usr/bin/env -S uv run --script
"""Collect professional ratings for albums linked from a musician's Wikipedia page.

Given the URL of a Wikipedia article about a musician, find every album
*linked* in the article's Discography section (album/work titles are wiki-links
wrapped in italics), open each album's page, read its "Professional ratings"
box, and report every reviewer's rating (AllMusic, the Penguin Guide, Rolling
Stone, Christgau, ...) as a CSV with one column per reviewer.
"""

import argparse
import contextlib
import csv
import re
import subprocess
import sys
import typing as t
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests  # ty: ignore[unresolved-import]
from bs4 import BeautifulSoup  # ty: ignore[unresolved-import]
from bs4 import Tag  # ty: ignore[unresolved-import]

WIKI = "https://en.wikipedia.org"
UA = "albumratings/1.0 (https://en.wikipedia.org; album rating collector)"

# Namespaces that are not articles (e.g. /wiki/File:..., /wiki/Category:...).
NAMESPACES = {
    "File", "Image", "Category", "Help", "Wikipedia", "Template",
    "Portal", "Special", "Talk", "User", "Module", "Draft", "MediaWiki",
}

# e.g. "4/5 stars", "4.5/5 stars", "3/4 stars" (Penguin Guide).
STARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+)\s+stars?", re.IGNORECASE)

# Phrases that mark the ratings box and rows within it that aren't reviewers.
BOX_MARKERS = ("professional ratings", "review scores")
SKIP_SOURCES = {"source", "aggregate scores", "review scores"}


class Album(t.NamedTuple):
    """An album linked from the discography."""

    title: str
    url: str


class Scored(t.NamedTuple):
    """An album together with its reviewer -> rating mapping."""

    title: str
    url: str
    scores: dict[str, str]  # reviewer name -> rating, e.g. {"AllMusic": "4/5"}


class AlbumRatings:
    """Scrape professional ratings for a musician's discography."""

    parser: argparse.ArgumentParser
    args: argparse.Namespace
    session: requests.Session

    def parse_cli(self) -> None:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "url",
            help="URL of the musician's Wikipedia article",
        )
        parser.add_argument(
            "-o",
            "--output",
            default="-",
            help="Write CSV here (default: stdout)",
        )
        parser.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Include albums with no ratings found",
        )
        parser.add_argument(
            "-j",
            "--jobs",
            type=int,
            default=8,
            help="Number of album pages to fetch in parallel",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Report progress on stderr",
        )
        parser.add_argument(
            "-O",
            "--open",
            action="store_true",
            help="Open after writing",
        )
        self.args = parser.parse_args()
        self.parser = parser

    def fail(self, msg: str) -> t.Never:
        """Fail because of the user."""
        self.parser.error(msg)

    def log(self, *msg: object) -> None:
        """Print progress to stderr when verbose."""
        if self.args.verbose:
            print(*msg, file=sys.stderr)

    def main(self) -> None:
        """Collect and emit the ratings."""
        self.parse_cli()
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA

        albums = self.find_albums(self.args.url)
        if not albums:
            self.fail("No linked albums found in a Discography section.")
        self.log(f"Found {len(albums)} linked album(s); fetching ratings...")

        with ThreadPoolExecutor(max_workers=max(1, self.args.jobs)) as pool:
            scored = list(pool.map(self.rate_album, albums))

        if not self.args.all:
            scored = [s for s in scored if s.scores]
        self.emit(scored)

        if self.args.open:
            self.show_output()

    def emit(self, scored: list[Scored]) -> None:
        """Write a CSV with one column per reviewer, ordered by frequency."""
        reviewers = self.reviewer_columns(scored)
        with self.open_output() as fobj:
            writer = csv.writer(fobj)
            writer.writerow(["album", *reviewers, "url"])
            for s in scored:
                folded = {name.casefold(): rating for name, rating in s.scores.items()}
                row = [folded.get(name.casefold(), "") for name in reviewers]
                writer.writerow([s.title, *row, s.url])
        self.log(f"Wrote {len(scored)} row(s), {len(reviewers)} reviewer column(s).")

    @contextlib.contextmanager
    def open_output(self) -> t.Generator[t.TextIO]:
        """Return a writer for the output argument."""
        if self.args.output == "-":
            yield sys.stdout
        else:
            with Path(self.args.output).open("w", encoding="utf-8") as fobj:
                yield fobj

    def show_output(self) -> None:
        """Open the resulting .csv with the configure app."""
        if self.args.output == "-":
            print("Cannot open, file not written.")
        else:
            subprocess.run(["/usr/bin/open", self.args.output], check=False)

    def reviewer_columns(self, scored: list[Scored]) -> list[str]:
        """Reviewer column names, most-common first, merging case variants."""
        albums_per: Counter[str] = Counter()  # casefold key -> #albums
        spellings: dict[str, Counter[str]] = {}  # casefold key -> seen names
        for s in scored:
            for name in {n.casefold(): n for n in s.scores}.values():
                key = name.casefold()
                albums_per[key] += 1
                spellings.setdefault(key, Counter())[name] += 1
        keys = sorted(albums_per, key=lambda k: (-albums_per[k], k))
        return [spellings[k].most_common(1)[0][0] for k in keys]

    def find_albums(self, url: str) -> list[Album]:
        """Return albums linked (as italicised wiki-links) in Discography."""
        soup = self.get_soup(url)
        heading = self.find_discography_heading(soup)
        if heading is None:
            self.fail("No Discography section found on that page.")

        albums: dict[str, Album] = {}
        for node in self.section_nodes(heading):
            for italic in node.find_all("i"):
                for anchor in italic.find_all("a"):
                    album = self.anchor_to_album(anchor)
                    if album is not None:
                        albums.setdefault(album.url, album)
        return list(albums.values())

    def find_discography_heading(self, soup: BeautifulSoup) -> Tag | None:
        """Find the heading container of the Discography section."""
        for div in soup.select("div.mw-heading2"):
            if "discograph" in div.get_text().lower():
                return div
        return None

    def section_nodes(self, heading: Tag) -> t.Iterator[Tag]:
        """Yield sibling nodes from after a heading up to the next h2."""
        node = heading.find_next_sibling()
        while isinstance(node, Tag):
            classes = node.get("class") or []
            if node.name == "div" and "mw-heading2" in classes:
                return
            yield node
            node = node.find_next_sibling()

    def anchor_to_album(self, anchor: Tag) -> Album | None:
        """Turn a wiki-link into an Album, or None if it is not an article."""
        href = anchor.get("href") or ""
        if not href.startswith("/wiki/"):
            return None
        path = urllib.parse.unquote(href[len("/wiki/"):])
        page = path.split("#", 1)[0]
        if ":" in page and page.split(":", 1)[0] in NAMESPACES:
            return None
        title = anchor.get_text(strip=True) or page.replace("_", " ")
        return Album(title=title, url=WIKI + href)

    def rate_album(self, album: Album) -> Scored:
        """Fetch an album page and extract its professional ratings."""
        try:
            soup = self.get_soup(album.url)
        except requests.RequestException as exc:
            self.log(f"  ! {album.title}: {exc}")
            return Scored(album.title, album.url, {})
        scores = self.parse_ratings(soup)
        summary = ", ".join(f"{k} {v}" for k, v in scores.items()) or "(none)"
        self.log(f"  {album.title}: {summary}")
        return Scored(album.title, album.url, scores)

    BOX_COLUMNS = ("source", "rating")

    def parse_ratings(self, soup: BeautifulSoup) -> dict[str, str]:
        """Return {reviewer: rating} from the album's ratings box."""
        table = self.find_ratings_box(soup)
        if table is None:
            return {}
        scores: dict[str, str] = {}
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) != len(self.BOX_COLUMNS):
                continue
            source = self.cell_text(cells[0])
            if source.casefold() in SKIP_SOURCES:
                continue
            rating = self.cell_rating(row, cells[1])
            if source and rating:
                scores.setdefault(source, rating)
        return scores

    def find_ratings_box(self, soup: BeautifulSoup) -> Tag | None:
        """Find the "Professional ratings" / "Review scores" table."""
        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True).casefold()
            if any(marker in text for marker in BOX_MARKERS):
                return table
        return None

    def cell_rating(self, row: Tag, cell: Tag) -> str:
        """Rating from a row: star title ("4/5") if present, else cell text."""
        for element in row.find_all(name=True):
            match = STARS_RE.search(element.get("title") or "")
            if match:
                return match.group(1)
        return self.cell_text(cell)

    @staticmethod
    def cell_text(cell: Tag) -> str:
        """Text of a table cell, sans reference markers and stray spaces."""
        for sup in cell.find_all("sup"):
            sup.decompose()
        text = cell.get_text(" ", strip=True)
        text = re.sub(r"([(\[])\s+", r"\1", text)
        return re.sub(r"\s+([)\].,;])", r"\1", text)

    def get_soup(self, url: str) -> BeautifulSoup:
        """Fetch a URL and parse it."""
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")


if __name__ == "__main__":
    AlbumRatings().main()

# /// script
# requires-python = ">=3.14"
# dependencies = ["requests", "beautifulsoup4", "lxml"]
# ///
