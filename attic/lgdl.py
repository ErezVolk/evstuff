#!/usr/bin/env python3
"""Search and download from libgen."""
import argparse
import logging
import random
import re
import subprocess
import tomllib
import typing as t
import urllib.parse as urlparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import bs4  # type: ignore[import-untyped]
import requests  # type: ignore[import-untyped]
import requests.exceptions  # type: ignore[import-untyped]
import rich.logging  # type: ignore[import-untyped]
import rich.progress  # type: ignore[import-untyped]
from simple_term_menu import TerminalMenu  # type: ignore[import-untyped]

ANSI_BOLD = "\033[1m"
ANSI_CLEAR = "\033[0m"

__TODO__ = """
 -  save files for resume
 -  support annas-archive.org
"""


@dataclass
class IdCell:
    """Stuff in the "ID" cell of the query table."""

    lgid: int | None = None
    title: str = ""


@dataclass
class Hit:  # pylint: disable=too-many-instance-attributes
    """A query result."""

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
        """Preview for the selection menu."""
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
    """Raised when the HTML we get isn't what we expected."""


class LibgenDownload:
    """Simple Library Genesis search + download."""

    def parse_args(self) -> None:
        """Parse command-line."""
        parser = argparse.ArgumentParser(
            description="Search and download from libgen",
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
        parser.add_argument(
            "-f",
            "--fields",
            type=FullMatch("[tasyi]+"),
            help=(
                "One or more LibGen fields (*t*itle, *a*uthor, *s*eries, "
                "*y*ear, *i*sbn)"
            ),
        )
        parser.add_argument(
            "-t",
            "--topics",
            type=FullMatch("[lfcms]+"),
            help=(
                "One or more LibGen topics (*l*ibgen, *f*iction, *c*omics, "
                "*m*agazines, *s*tandards)"
            ),
        )
        parser.add_argument(
            "-c",
            "--contents",
            type=FullMatch("[f]*"),
            help=(
                "Zero or more LibGen objects (*l*ibgen, *f*iction, *c*omics, "
                "*m*agazines, *s*tandards)"
            ),
        )
        parser.add_argument(
            "-H",
            "--host",
            type=str,
            help="LibGen search host",
        )

        defaults = {
            "output": "libgen",
            "max_stem": 80,
            "fields": "tai",
            "topics": "fl",
            "contents": "f",
            "host": "libgen.gs",
        }
        for folder in [Path.home(), Path.cwd()]:
            path = folder / ".lgdlrc"
            try:
                with path.open("rb") as fobj:
                    defaults.update(tomllib.load(fobj))
            except FileNotFoundError:
                continue
            except tomllib.TOMLDecodeError:
                self.log.exception(path)
        parser.set_defaults(**defaults)

        self.args = parser.parse_args()
        self.query = " ".join(self.args.query)

    BAD_CHARS_RE = re.compile(r"[#%&{}<>*?!:@/\\|]")
    args: argparse.Namespace
    ext_col: str
    log: logging.Logger
    http: "Http"
    query: str
    progress: rich.progress.Progress

    def run(self) -> None:
        """Entry point."""
        self.parse_args()
        self.configure_logging()

        self.http = Http(self.args.user_agent, log=self.log)
        hits = self.run_query()
        if not hits:
            self.log.info("No hits; better luck next time!")
            return

        # Resumables first, then alphabetically
        hits.sort(key=lambda hit: (not hit.resume, hit.name.lower()))

        choices = self.choose(hits)
        if not choices:
            self.log.info("Nothing selected; better luck next time!")
            return

        self.args.output.mkdir(parents=True, exist_ok=True)
        with DownloadProgress() as self.progress:
            for nhit in choices:
                self.download(hits[nhit])

    def configure_logging(self) -> None:
        """Set logging format and level."""
        level = logging.DEBUG if self.args.debug else logging.INFO
        logging.basicConfig(
            format="%(message)s",
            datefmt="[%X]",
            level=level,
            handlers=[rich.logging.RichHandler()],
        )
        self.log = logging.getLogger("lgdl")

    def run_query(self) -> list[Hit]:
        """Search LibGen and grok the result."""
        html = self.get_query_reply()
        hits = self.get_raw_hits(html)

        # Only files we CAN download
        hits = list(filter(lambda hit: hit.mirrors, hits))

        if not self.args.overwrite:
            # Only files we SHOULD download
            hits = list(filter(lambda hit: not hit.path.is_file(), hits))

        return hits

    def get_query_reply(self) -> str:
        """Run the LibGen query and return the raw HTML."""
        if self.args.reload:
            # Don't really search (useful for debugging)
            with self.open_dump("query", "html", "r") as fobj:
                return fobj.read()

        params = [
            ("req", self.query),
            ("order", "author"),
            ("res", "100"),  # Results per page
            ("gmode", "on"),  # Google mode
            ("filesuns", "all"),
        ] + [
            ("fields[]", field)
            for field in self.args.fields
        ] + [
            ("topics[]", topic)
            for topic in self.args.topics
        ] + [
            ("objects[]", content)
            for content in self.args.contents
        ]
        url = f"https://{self.args.host}/index.php?" + "&".join(
            f"{urlparse.quote(name)}={urlparse.quote(value)}"
            for name, value in params
        )

        response = self.http.get(url)
        return response.text

    def get_raw_hits(self, html: str) -> list[Hit]:
        """Parse query results and return all items, even unwanted ones."""
        soup = self.parse_html(html, "query")

        # Special case: zero hits found
        for atag in soup.find_all("a", class_="nav-link"):
            if atag.get_text().strip() == "Files 0":
                self.log.debug("Zero hits")
                return []

        # In v1, the table has an ID, so that's easy
        table = soup.find("table", id="tablelibgen")
        if isinstance(table, bs4.Tag):
            return self.get_raw_hits_v1(table)

        # In v2, the table is harder to find an parse
        for table in soup.find_all("table", attrs={"class": "c"}):
            if isinstance(table, bs4.Tag):
                return self.get_raw_hits_v2(table)

        self.log.error("Cannot find table in HTML")
        return []

    def get_raw_hits_v1(
        self,
        table: bs4.Tag,
    ) -> list[Hit]:
        """Convert v1 (libgen.gs) table to hits."""
        try:
            columns = [
                next(col.strings).strip()
                for col in self.find_tag(table, "thead").find_all("th")
            ]
            self.ext_col = "Ext."
            self.check_columns(columns)

            return [
                self.parse_row(row, columns)
                for row in self.find_tag(table, "tbody").find_all("tr")
            ]
        except WrongReplyError as wre:
            self.log.debug("Unexpected HTML returned from query: %s", wre)
            return []

    def get_raw_hits_v2(
        self,
        table: bs4.Tag,
    ) -> list[Hit]:
        """Convert v2 (libgen.is) table to hits."""
        try:
            columns = None
            hits: list[Hit] = []

            for row in table.find_all("tr"):
                if columns is None:
                    # First row has the column names
                    columns = [
                        col.get_text(strip=True)
                        for col in row.find_all("td")
                    ]
                    self.ext_col = "Extension"
                    self.check_columns(columns)
                else:
                    hits.append(self.parse_row(row, columns))
        except WrongReplyError as wre:
            self.log.debug("Unexpected HTML returned from query: %s", wre)
            return []
        else:
            return hits

    def check_columns(self, columns: list[str]) -> None:
        """Make sure the query table is well-formed."""
        missing = {"ID", "Author(s)", self.ext_col, "Mirrors"} - set(columns)
        if missing:
            self.log.debug("Columns are %s", columns)
            self.log.debug("Missing: %s", list(missing))
            raise WrongReplyError("Incorrect table columns")

    def choose(self, hits: list[Hit]) -> Sequence[int]:
        """Ask the user what to download."""
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
        """Download one file, trying all mirrors."""
        self.log.info("%s (%s)", hit.name, hit.size_desc)
        self.log.debug("%s (%d mirror(s))", hit.work_path, len(hit.mirrors))

        for mirror in hit.mirrors:
            if self.download_mirror(hit, mirror):
                hit.work_path.rename(hit.path)
                if self.args.view:
                    self.log.debug("Trying to open %s", hit.path)
                    subprocess.run(["open", str(hit.path)], check=False)
                return

        try:
            if hit.work_path.stat().st_size == 0:
                hit.work_path.unlink()
        except FileNotFoundError:
            pass

        self.log.info(
            "%s: Could not download (number of mirrors: %d)",
            hit.name,
            len(hit.mirrors),
        )
        for nmirror, mirror in enumerate(hit.mirrors, 1):
            self.log.debug("Mirror %d: %s", nmirror, mirror)

    def download_mirror(self, hit: Hit, mirror: str) -> bool:
        """Download one file from a specific mirror."""
        self.log.debug("Mirror: %s", urlparse.urlsplit(mirror).netloc)

        try:
            self.http.download(
                progress=self.progress,
                description=hit.name,
                url=self.read_mirror(mirror),
                path=hit.work_path,
                overwrite=self.args.overwrite,
            )
        except (requests.exceptions.RequestException, WrongReplyError) as exc:
            self.log.debug("Error downloading: %s", exc)
            return False
        else:
            return True

    def read_mirror(self, url: str) -> str:
        """Read LibGen mirror page, return download URL."""
        response = self.http.get(url)
        soup = self.parse_html(response.text, "mirror")
        atag = self.find_tag(soup, "a", string="GET")
        href = atag.get("href")

        if not isinstance(href, str):
            raise WrongReplyError("No GET hyperlink")

        return urlparse.urljoin(url, href)

    def parse_row(self, row: bs4.Tag, columns: list[str]) -> Hit:
        """Convert a query table row to a dict."""
        cells = dict(zip(columns, row.find_all("td"), strict=True))
        if "Title" in cells:
            id_cell = IdCell(
                lgid=int(self.parse_cell(cells["ID"])),
                title=self.parse_cell(cells["Title"]),
            )
        else:
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

        ext = self.parse_cell(cells[self.ext_col])
        if ext:
            name = f"{name}.{ext}"

        name = self.BAD_CHARS_RE.sub("-", name)

        mirrors = [
            url for url in self.parse_mirrors_cell(cells["Mirrors"])
            if "annas-archive.org" not in url
        ]
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
            self.log.debug("Hm, no title: %s", cell)

        for span in cell.find_all("span", class_="badge-secondary"):
            text = span.get_text(strip=True)
            mobj = re.fullmatch(r"[a-z] ([\d]+)", text)
            if mobj:
                id_cell.lgid = int(mobj.group(1))
                break
        else:
            self.log.debug("Hm, no LibGen ID: %s", cell)

        return id_cell

    def parse_mirrors_cell(self, cell: bs4.Tag) -> list[str]:
        """Extract links from the Mirrors cell."""
        base = f"https://{self.args.host}/"
        return [
            urlparse.urljoin(base, href)
            for link in cell.find_all("a")
            if isinstance(href := link.get("href"), str)
        ]

    def parse_cell(self, cell: bs4.Tag | None) -> str:
        """'Parse' a plain cell."""
        if cell is None:  # Optional cell wasn't there
            return ""
        return cell.get_text(strip=True)

    def find_tag(self, tag: bs4.Tag, name: str, **kwargs) -> bs4.Tag:
        """Sanity-checking wrapper for `Tag.find()`."""
        found = tag.find(name, **kwargs)
        if not isinstance(found, bs4.Tag):
            raise WrongReplyError(f"No <{name}> in reply")
        return found

    def parse_html(self, html: str, infix: str) -> bs4.BeautifulSoup:
        """Debug-dumping wrapper around BeautifulSoup."""
        if self.args.debug and infix:
            with self.open_dump(infix, "html", "w") as fobj:
                fobj.write(html)
        return bs4.BeautifulSoup(html, "html.parser")

    def open_dump(self, infix: str, suffix: str, mode: str) -> t.IO:
        """Open a dump file created by `parse_html()`."""
        return open(f"lgdl-{infix}.{suffix}", mode, encoding="utf-8")


class FullMatch:  # pylint: disable=too-few-public-methods
    """Validator for argument that takes a regular expression."""

    def __init__(self, expr: str) -> None:
        self.expr = expr

    def __call__(self, value: str) -> str:
        """Validate."""
        if not re.fullmatch(self.expr, value):
            raise ValueError
        return value


@dataclass
class Marquee:
    """A download marquee."""

    WIDTH = 24

    description: str
    offset: int = 0
    forward: bool = False

    def step(self) -> str:
        """Advance the marquee."""
        if self.forward:
            if self.offset + self.WIDTH < len(self.description):
                self.offset = self.offset + 1
            else:
                self.forward = False
        elif self.offset > 0:
            self.offset = self.offset - 1
        else:
            self.forward = True
        limit = self.offset + self.WIDTH
        return self.description[self.offset:limit]


class DownloadProgress(rich.progress.Progress):
    """A marquee-displaying download progress element."""

    def __init__(self) -> None:
        self.marquees: dict[rich.progress.TaskID, Marquee] = {}
        super().__init__(
            rich.progress.TextColumn(
                "[bold]{task.description}",
                justify="right",
            ),
            rich.progress.BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            rich.progress.DownloadColumn(),
            "•",
            rich.progress.TransferSpeedColumn(),
            "•",
            rich.progress.TimeRemainingColumn(),
        )

    def add_task(
        self,
        description: str,
        *args,
        **kwargs,
    ) -> rich.progress.TaskID:
        """Add a task and, if long enough, a marquee."""
        if len(description) <= Marquee.WIDTH:
            return super().add_task(description, *args, **kwargs)

        marquee = Marquee(description)
        task_id = super().add_task(marquee.step(), *args, **kwargs)
        self.marquees[task_id] = marquee
        return task_id

    def stop_task(self, task_id: rich.progress.TaskID) -> None:
        """Stop task and marquee."""
        self.marquees.pop(task_id, None)

    def get_renderable(self):
        """Do the marquee."""
        for task_id, marquee in self.marquees.items():
            self.update(task_id, description=marquee.step())
        return super().get_renderable()


class Http:
    """Wrapper+ for `requests.get()`."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "QtWebEngine/5.15.5 "
        "Chrome/87.0.4280.144 "
        "Safari/537.36"
    )
    log: logging.Logger

    def __init__(
        self,
        user_agent: str | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self.log = log or logging.getLogger()
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.log.debug("User-Agent: %s", self.user_agent)

    def get(
        self,
        url: str,
        pos: int = 0,
        *,
        stream: bool = False,
    ) -> requests.Response:
        """Override parent."""
        headers = {"User-Agent": self.user_agent}
        if pos:
            headers["Range"] = f"bytes={pos}-"
        resp = requests.get(url, headers=headers, stream=stream, timeout=60)
        resp.raise_for_status()
        return resp

    def download(  # pylint: disable=too-many-arguments
        self,
        url: str,
        *,
        path: Path,
        overwrite: bool,
        progress: rich.progress.Progress,
        description: str,
    ) -> None:
        """Download a file."""
        task_id = progress.add_task(description)
        try:
            progress.console.log(description)

            with path.open("wb" if overwrite else "ab") as fobj:
                got = fobj.tell()
                if got > 0:
                    self.log.debug("Resuming at %s", self.kbmbgb(got))
                    progress.update(task_id, completed=got, total=got * 2)

                response = self.get(url, pos=got, stream=True)
                size = got + int(response.headers.get("content-length", 0))
                progress.update(task_id, total=size, completed=got)
                for chunk in response.iter_content():
                    progress.update(task_id, advance=len(chunk))
                    fobj.write(chunk)

                got = fobj.tell()

            if got < size:
                raise WrongReplyError(
                    f"File terminated prematurely ("
                    f"{self.kbmbgb(got)} < "
                    f"{self.kbmbgb(size)}",
                )
        finally:
            progress.stop_task(task_id)

    @staticmethod
    def kbmbgb(num: float) -> str:
        """Format a number as "932K", etc."""
        prefixes = ["", "K", "M", "G", "T"]
        for prefix in prefixes:
            if abs(num) < 9.995:
                return f"{num:,.2f}{prefix}"
            if abs(num) < 99.95:
                return f"{num:,.1f}{prefix}"
            if abs(num) < 999.5:
                return f"{num:,.0f}{prefix}"
            num = num / 1000
        return f"{num:,.1f}{prefixes[-1]}"


if __name__ == "__main__":
    LibgenDownload().run()
