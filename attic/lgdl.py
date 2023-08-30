#!/usr/bin/env python3
"""Search and download from libgen"""
import argparse
import contextlib
from dataclasses import dataclass
import logging
from pathlib import Path
import random
import re
import subprocess
import tomllib
import urllib.parse as urlparse

from collections.abc import Sequence

import bs4
import requests
import requests.exceptions
from simple_term_menu import TerminalMenu
from tqdm import tqdm

ANSI_BOLD = "\033[1m"
ANSI_CLEAR = "\033[0m"


@dataclass
class IdCell:
    """Stuff in the "ID" cell of the query table"""
    lgid: int | None = None
    title: str = ""


@dataclass
class Hit:  # pylint: disable=too-many-instance-attributes
    """A query result"""
    title: str
    lgid: int | None
    authors: str
    name: str
    path: Path
    work_path: Path
    resume: bool
    language: str
    size_desc: str
    publisher: str
    year: str
    pages: str
    mirrors: list[str]

    def preview(self) -> str:
        """Preview for the selection menu"""
        vals = {
            "LibGen ID": self.lgid,
            "Title": self.title,
            "Author(s)": self.authors,
            "Publisher": self.publisher,
            "Year": self.year,
            "Language": self.language,
            "Pages": self.pages if self.pages != "0" else "",
            "Size": self.size_desc,
            "Mirrors": len(self.mirrors),
        }
        lines = [
            f"{key}: {ANSI_BOLD}{value}{ANSI_CLEAR}"
            for key, value in vals.items()
            if value
        ]
        if self.resume:
            lines.append("* Will resume partial download")
        return "\n".join(lines)


class WrongReplyError(RuntimeError):
    """Raised when the HTML we get isn't what we expected"""


class LibgenDownload:
    """Simple Library Genesis search + download"""

    def parse_args(self):
        """Usage"""
        parser = argparse.ArgumentParser(
            description="Search and download from libgen"
        )
        parser.add_argument(
            "query",
            metavar="QUERY",
            nargs="+",
            help="what to search for",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            help="where to save files",
        )
        parser.add_argument(
            "-O",
            "--overwrite",
            action="store_true",
            help="Re-download existing files",
        )
        parser.add_argument(
            "-m",
            "--max-stem",
            type=int,
            help="truncate file names to this length",
        )
        parser.add_argument(
            "-v",
            "--view",
            action="store_true",
            help="open files after downloading",
        )
        parser.add_argument(
            "-u",
            "--user-agent",
            help="User-Agent string for HTTP requests",
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="print more info, create more files",
        )
        parser.add_argument(
            "-D",
            "--reload",
            action="store_true",
            help="don't query, read the results file from a previous -d run",
        )

        defaults = {"output": "libgen", "max_stem": 80}
        for folder in [Path.home(), Path.cwd()]:
            try:
                with open(folder / ".lgdlrc", "rb") as fobj:
                    defaults.update(tomllib.load(fobj))
            except (FileNotFoundError, tomllib.TOMLDecodeError):
                pass
        parser.set_defaults(**defaults)

        self.args = parser.parse_args()
        self.query = " ".join(self.args.query)

    BAD_CHARS_RE = re.compile(r"[#%&{}<>*?!:@/\\]")
    args: argparse.Namespace
    http: "Http"
    query: str

    def run(self):
        """Entry point"""
        self.parse_args()
        self.configure_logging()

        self.http = Http(self.args.user_agent)
        hits = self.run_query()
        if not hits:
            logging.info("No hits; better luck next time!")
            return

        # Resumables first, then alphabetically
        hits.sort(key=lambda hit: (not hit.resume, hit.name.lower()))

        choices = self.choose(hits)
        if not choices:
            logging.info("Nothing selected; better luck next time!")
            return

        self.args.output.mkdir(parents=True, exist_ok=True)
        for nhit in choices:
            self.download(hits[nhit])

    def configure_logging(self):
        """Set logging format and level"""
        if self.args.debug:
            fmt = "%(asctime)s %(message)s"
            level = logging.DEBUG
        else:
            fmt = "%(message)s"
            level = logging.INFO
        logging.basicConfig(format=fmt, level=level)

    def run_query(self) -> list[Hit]:
        """Search LibGen and grok the result"""
        html = self.get_query_reply()
        hits = self.get_raw_hits(html)

        # Only files we CAN download
        hits = list(filter(lambda hit: hit.mirrors, hits))

        if not self.args.overwrite:
            # Only files we SHOULD download
            hits = list(filter(lambda hit: not hit.path.is_file(), hits))

        return hits

    def get_query_reply(self) -> str:
        """Run the LibGen query and return the raw HTML"""
        if self.args.reload:
            # Don't really search (useful for debugging)
            with self.open_dump("query", "html", "r") as fobj:
                return fobj.read()

        params = (
            ("req", self.query),
            ("columns[]", "t"),  # (search in fields) Title
            ("columns[]", "a"),  # (search in fields) Author
            # ("columns[]", "s"),  # (search in fields) Series
            # ("columns[]", "y"),  # (search in fields) Year
            ("columns[]", "i"),  # (search in fields) ISBN
            ("objects[]", "f"),  # (search in objects): Files
            ("topics[]", "l"),  # (search in topics): Libgen
            ("topics[]", "f"),  # (search in topics): Fiction
            ("order", "author"),
            ("res", "100"),  # Results per page
            ("gmode", "on"),  # Google mode
            ("filesuns", "all"),
        )
        url = "https://libgen.gs/index.php?" + "&".join(
            f"{urlparse.quote(name)}={urlparse.quote(value)}"
            for name, value in params
        )

        response = self.http.get(url)
        return response.text

    def get_raw_hits(self, html: str) -> list[Hit]:
        """Parse query results and return all items, even ones we don't want"""
        try:
            soup = self.parse_html(html, "query")
            table = self.find_tag(soup, "table", id="tablelibgen")

            columns = [
                next(col.strings).strip()
                for col in self.find_tag(table, "thead").find_all("th")
            ]
            missing = {"ID", "Author(s)", "Ext.", "Mirrors"} - set(columns)
            if missing:
                logging.debug("Columns are %s", columns)
                logging.debug("Missing: %s", list(missing))
                raise WrongReplyError("Incorrect table columns")

            return [
                self.parse_row(row, columns)
                for row in self.find_tag(table, "tbody").find_all("tr")
            ]
        except WrongReplyError as wre:
            logging.debug("Unexpected HTML returned from query: %s", wre)
            return []

    def choose(self, hits: list[Hit]) -> Sequence[int]:
        """Ask the user what to download"""
        menu = TerminalMenu(
            [
                f"{'* ' if hit.resume else ''}{hit.name} "
                f"({hit.language}, {hit.size_desc})"
                f"|{nhit}"
                for nhit, hit in enumerate(hits)
            ],
            title=f"LibGen query: {self.query}",
            multi_select=True,
            show_multi_select_hint=True,
            preview_command=lambda nhit_str: hits[int(nhit_str)].preview(),
            preview_title="File",
        )
        choices = menu.show()
        if not isinstance(choices, Sequence):
            return []
        return choices

    def download(self, hit: Hit):
        """Download one file, trying all mirrors"""
        logging.info("%s (%s)", hit.name, hit.size_desc)
        logging.debug("%s (%d mirror(s))", hit.work_path, len(hit.mirrors))

        for mirror in hit.mirrors:
            if self.download_mirror(hit, mirror):
                hit.work_path.rename(hit.path)
                if self.args.view:
                    logging.debug("Trying to open %s", hit.path)
                    subprocess.run(["open", str(hit.path)], check=False)
                return

        logging.info("%s: Could not download", hit.name)

    def download_mirror(self, hit: Hit, mirror: str) -> bool:
        """Download one file from a specific mirror"""
        logging.debug("Mirror: %s", urlparse.urlsplit(mirror).netloc)

        try:
            self.http.download(
                url=self.read_mirror(mirror),
                path=hit.work_path,
                overwrite=self.args.overwrite,
            )
            return True
        except (requests.exceptions.RequestException, WrongReplyError) as exc:
            logging.debug("Error downloading: %s", exc)
            return False

    def read_mirror(self, url: str) -> str:
        """Read LibGen mirror page, return download URL"""
        response = self.http.get(url)
        soup = self.parse_html(response.text, "mirror")
        atag = self.find_tag(soup, "a", string="GET")
        href = atag.get("href")

        if not isinstance(href, str):
            raise WrongReplyError("No GET hyperlink")

        return urlparse.urljoin(url, href)

    def parse_row(self, row: bs4.Tag, columns: list[str]) -> Hit:
        """Convert a query table row to a dict"""
        cells = dict(zip(columns, row.find_all("td")))
        id_cell = self.parse_id_cell(cells["ID"])
        name = id_cell.title
        author = authors = self.parse_cell(cells["Author(s)"])
        if author == "coll.":
            author = ""
        if not author and ": " in name:
            author, name = name.split(": ", 1)
        if author:
            author = author.split(",", 1)[0]
            author = author.split(";", 1)[0]
            author = author.strip()
            name = f"{author} - {name}"

        if self.args.max_stem:
            name = name[:self.args.max_stem].strip()

        ext = self.parse_cell(cells["Ext."])
        if ext:
            name = f"{name}.{ext}"

        name = self.BAD_CHARS_RE.sub("-", name)

        mirrors = self.parse_mirrors_cell(cells["Mirrors"])
        random.shuffle(mirrors)  # Keep them on their toes

        path = self.args.output / name
        if id_cell.lgid:
            work_path = self.args.output / f"libgen-{id_cell.lgid}.lgdl"
        else:
            work_path = self.args.output / f"{name}.lgdl"

        return Hit(
            title=id_cell.title,
            lgid=id_cell.lgid,
            authors=authors,
            name=name,
            path=path,
            work_path=work_path,
            resume=not self.args.overwrite and work_path.is_file(),
            mirrors=mirrors,
            language=self.parse_cell(cells.get("Language")),
            size_desc=self.parse_cell(cells.get("Size")),
            publisher=self.parse_cell(cells.get("Publisher")),
            year=self.parse_cell(cells.get("Year")),
            pages=self.parse_cell(cells.get("Pages")),
        )

    def parse_id_cell(self, cell: bs4.Tag) -> IdCell:
        """Extract the information we want from the ID cell"""
        id_cell = IdCell()

        for link in cell.find_all("a"):
            title = link.get_text().strip(". ")
            if title:
                id_cell.title = title
                break
        else:
            logging.debug("Hm, no title: %s", cell)

        for span in cell.find_all("span", class_="badge-secondary"):
            text = span.get_text(strip=True)
            mobj = re.fullmatch(r"[a-z] ([\d]+)", text)
            if mobj:
                id_cell.lgid = int(mobj.group(1))
                break
        else:
            logging.debug("Hm, no LibGen ID: %s", cell)

        return id_cell

    def parse_mirrors_cell(self, cell: bs4.Tag) -> list[str]:
        """Extract links from the Mirrors cell"""
        return [
            href
            for link in cell.find_all("a")
            if isinstance(href := link.get("href"), str)
        ]

    def parse_cell(self, cell: bs4.Tag | None) -> str:
        """'Parse' a plain cell"""
        if cell is None:  # Optional cell wasn't there
            return ""
        return cell.get_text(strip=True)

    def find_tag(self, tag: bs4.Tag, name: str, *args, **kwargs) -> bs4.Tag:
        """Sanity-checking wrapper for `Tag.find()`"""
        found = tag.find(name, *args, **kwargs)
        if not isinstance(found, bs4.Tag):
            raise WrongReplyError(f"No <{name}> in reply")
        return found

    def parse_html(self, html: str, infix=None) -> bs4.BeautifulSoup:
        """Debug-dumping wrapper around BeautifulSoup"""
        if self.args.debug and infix:
            with self.open_dump(infix, "html", "w") as fobj:
                fobj.write(html)
        return bs4.BeautifulSoup(html, "html.parser")

    def open_dump(self, infix: str, suffix: str, mode: str):
        """Open a dump file created by `parse_html()`"""
        return open(f"lgdl-{infix}.{suffix}", mode, encoding="utf-8")


class Http:
    """Wrapper+ for `requests.get()`"""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "QtWebEngine/5.15.5 "
        "Chrome/87.0.4280.144 "
        "Safari/537.36"
    )

    def __init__(self, user_agent: str | None = None):
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        logging.debug("User-Agent: %s", self.user_agent)

    def get(self, url, pos=0, stream=False) -> requests.Response:
        """Wrapper for `requests.get()`"""
        headers = {"User-Agent": self.user_agent}
        if pos:
            headers["Range"] = f"bytes={pos}-"
        resp = requests.get(url, headers=headers, stream=stream, timeout=60)
        resp.raise_for_status()
        return resp

    def download(self, url: str, path: Path, overwrite: bool):
        """Download a file"""
        with open(path, "wb" if overwrite else "ab") as fobj:
            got = fobj.tell()
            if got > 0:
                logging.debug("Resuming at %s", tqdm.format_sizeof(got))

            response = self.get(url, pos=got, stream=True)
            size = got + int(response.headers.get("content-length", 0))
            with ProgressBar(initial=got, total=size) as progress:
                for chunk in response.iter_content():
                    progress.update(len(chunk))
                    fobj.write(chunk)

            got = fobj.tell()

        if got < size:
            raise WrongReplyError(
                f"File terminated prematurely ("
                f"{tqdm.format_sizeof(got)} < "
                f"{tqdm.format_sizeof(size)}"
            )


class ProgressBar(contextlib.ExitStack):
    """Self-closing wrapper around `tqdm`."""

    def __init__(self, initial: int, total: int, unit="iB", unit_scale=True):
        super().__init__()
        self._tqdm = tqdm(
            initial=initial,
            total=total,
            unit=unit,
            unit_scale=unit_scale,
        )
        self.callback(self._tqdm.close)

    def update(self, amount: int):
        """Just a wrapper"""
        self._tqdm.update(amount)


if __name__ == "__main__":
    LibgenDownload().run()
