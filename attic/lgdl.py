#!/usr/bin/env python3
"""Search and download from libgen"""
import argparse
from dataclasses import dataclass
from pathlib import Path
import random
import re
import urllib.parse

import bs4
import requests
import requests.exceptions
from simple_term_menu import TerminalMenu
from tqdm import tqdm


@dataclass
class IdCell:
    """Stuff in the "ID" cell of the query table"""
    lgid: int | None = None
    title: str = ""


@dataclass
class Hit:
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


class WrongReplyError(RuntimeError):
    """Raised when the HTML we get isn't what we expected"""


class LibgenDownload:
    """Simple Library Genesis search + download"""
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "QtWebEngine/5.15.5 "
        "Chrome/87.0.4280.144 "
        "Safari/537.36"
    )
    BAD_CHARS_RE = re.compile(r"[#%&{}<>*?!:@\\]")
    ANSI_BOLD = "\033[1m"
    ANSI_CLEAR = "\033[0m"
    args: argparse.Namespace

    def parse_cli(self):
        """Usage"""
        parser = argparse.ArgumentParser(
            description="Search and download from libgen"
        )
        parser.add_argument(
            "query",
            metavar="QUERY",
            help="what to search for",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            default=Path("libgen"),
            help="where to save files",
        )
        parser.add_argument(
            "-O",
            "--overwrite",
            action="store_true",
            help="Re-download existing files",
        )
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="write some messages and debugging files",
        )
        parser.add_argument(
            "-D",
            "--reload",
            action="store_true",
            help="don't query, read the results file from a previous -d run",
        )
        self.args = parser.parse_args()

    def run(self):
        """Entry point"""
        self.parse_cli()
        hits = self.run_query()
        if not hits:
            print("Better luck searching next time!")
            return

        hits.sort(key=lambda hit: (not hit.resume, hit.name.lower()))

        choices = self.choose(hits)
        if not choices:
            print("Better luck picking next time!")
            return

        for choice in choices:
            self.download(hits[choice])

    def run_query(self) -> list[Hit]:
        """Search LibGen and grok the result"""
        html = self.get_query_reply()
        hits = self.get_raw_hits(html)

        hits = [
            hit for hit in hits
            if hit.mirrors  # Only things we CAN download
        ]
        if not self.args.overwrite:
            hits = [
                hit for hit in hits
                if not hit.path.is_file()  # Only things we SHOULD download
            ]
        return hits

    def get_query_reply(self) -> str:
        """Run the LibGen query and return the raw HTML"""
        if self.args.reload:
            with open("lgdl-query.html", encoding="utf-8") as fobj:
                return fobj.read()

        params = (
            ("req", self.args.query),
            ("columns[]", "t"),  # (search in fields) Title
            ("columns[]", "a"),  # (search in fields) Author
            # ("columns[]", "s"),  # (search in fields) Series
            # ("columns[]", "y"),  # (search in fields) Year
            ("columns[]", "i"),  # (search in fields) ISBN
            ("objects[]", "f"),  # (search in objects): Files
            ("topics[]", "l"),  # (search in topics): Libgen
            ("topics[]", "f"),  # (search in topics): Fiction
            # ("order", "year"),
            ("order", "author"),
            ("res", "100"),  # Results per page
            ("gmode", "on"),  # Google mode
            ("filesuns", "all"),
        )
        url = "https://libgen.gs/index.php?" + "&".join(
            f"{urllib.parse.quote(name)}={urllib.parse.quote(value)}"
            for name, value in params
        )

        response = self.http_get(url)
        html = response.text
        if self.args.debug:
            with open("lgdl-query.html", "w", encoding="utf-8") as fobj:
                fobj.write(html)
        return html

    def get_raw_hits(self, html: str) -> list[Hit]:
        """Parse query results and return all items, even ones we don't want"""
        try:
            soup = bs4.BeautifulSoup(html, "html.parser")
            table = self.find_tag(soup, "table", id="tablelibgen")

            columns = [
                next(col.strings).strip()
                for col in self.find_tag(table, "thead").find_all("th")
            ]
            return [
                self.parse_row(row, columns)
                for row in self.find_tag(table, "tbody").find_all("tr")
            ]
        except WrongReplyError:
            print("Unexpected HTML returned from query")
            return []

    def choose(self, hits: list[Hit]) -> list[int]:
        """Ask the user what to download"""
        def preview(nhit: str) -> str:
            hit = hits[int(nhit)]
            vals = {
                "LibGen ID": hit.lgid,
                "Title": hit.title,
                "Author(s)": hit.authors,
                "Publisher": hit.publisher,
                "Year": hit.year,
                "Language": hit.language,
                "Pages": hit.pages,
                "Size": hit.size_desc,
                "Mirrors": len(hit.mirrors),
            }
            lines = [
                f"{key}: {self.ANSI_BOLD}{value}{self.ANSI_CLEAR}"
                for key, value in vals.items()
                if value
            ]
            if hit.resume:
                lines.append("* Will resume partial download")
            return "\n".join(lines)

        menu = TerminalMenu(
            [
                f"{'* ' if hit.resume else ''}{hit.name} "
                f"({hit.language}, {hit.size_desc})"
                f"|{nhit}"
                for nhit, hit in enumerate(hits)
            ],
            title="Select LibGen item(s)",
            multi_select=True,
            show_multi_select_hint=True,
            preview_command=preview,
            preview_title="File",
        )
        return menu.show()

    def download(self, hit: Hit):
        """Download one file, trying all mirrors"""
        mirrors = hit.mirrors
        if len(mirrors) > 1:
            msg = f"{hit.name} ({hit.size_desc}) ({len(mirrors)} mirror(s))"
        else:
            msg = f"{hit.name} ({hit.size_desc})"
        print(msg, flush=True)

        for mirror in mirrors:
            if self.download_mirror(hit, mirror):
                hit.work_path.rename(hit.path)
                return
        print(f"{hit.name}: Could not download")

    def download_mirror(self, hit: Hit, mirror: str) -> bool:
        """Download one file from a specific mirror"""
        progress = None
        work_path = hit.work_path

        try:
            url = self.read_mirror(mirror)
            if not url:
                return False

            # Are we continuing?
            if hit.resume:
                pos = work_path.stat().st_size
                mode = "ab"
                if self.args.debug:
                    print(f"Resuming download at {tqdm.format_sizeof(pos)}...")
            else:
                self.args.output.mkdir(parents=True, exist_ok=True)
                pos = 0
                mode = "wb"

            # Read the actual thing
            response = self.http_get(
                url,
                pos=pos,
                stream=True,
            )

            size = int(response.headers.get("content-length", 0))
            progress = tqdm(
                initial=pos,
                total=pos + size,
                unit="iB",
                unit_scale=True,
            )

            with open(work_path, mode) as fobj:
                for chunk in response.iter_content():
                    progress.update(len(chunk))
                    fobj.write(chunk)
        except requests.exceptions.ReadTimeout:
            if self.args.debug:
                print("Timeout during HTTP GET")
            return False
        finally:
            if progress is not None:
                progress.close()

        return True

    def read_mirror(self, mirror_url: str) -> str:
        """Read LibGen mirror page, return download URL"""
        response = self.http_get(mirror_url)
        mirror_html = response.text
        if self.args.debug:
            with open("lgdl-mirror.html", "w", encoding="utf-8") as fobj:
                fobj.write(mirror_html)
        soup = bs4.BeautifulSoup(mirror_html, "html.parser")
        try:
            link = self.find_tag(soup, "a", string="GET")
            href = link["href"]
            if not isinstance(href, str):
                raise WrongReplyError()
        except (WrongReplyError, KeyError):
            return ""

        return urllib.parse.urljoin(mirror_url, href)

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

        ext = self.parse_cell(cells["Ext."])
        if ext:
            name = f"{name}.{ext}"

        name = self.BAD_CHARS_RE.sub("-", name)

        mirrors = self.parse_mirrors_cell(cells["Mirrors"])
        random.shuffle(mirrors)

        path = self.args.output / f"{name}"
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
            language=self.parse_cell(cells["Language"]),
            size_desc=self.parse_cell(cells["Size"]),
            publisher=self.parse_cell(cells["Publisher"]),
            year=self.parse_cell(cells["Year"]),
            pages=self.parse_cell(cells["Pages"]),
        )

    def parse_id_cell(self, cell: bs4.Tag) -> IdCell:
        """Extract the information from the ID cell"""
        id_cell = IdCell()
        for link in cell.find_all("a"):
            if (title := link.get_text().strip(". ")):
                id_cell.title = title
                break
        for span in cell.find_all("span", class_="badge-secondary"):
            text = span.get_text(strip=True)
            if (match := re.fullmatch(r"[a-z] ([\d]+)", text)):
                id_cell.lgid = int(match.group(1))
        return id_cell

    def parse_mirrors_cell(self, cell: bs4.Tag) -> list[str]:
        """Extract links from the Mirrors cell"""
        return [
            href
            for link in cell.find_all("a")
            if isinstance(href := link["href"], str)
        ]

    def parse_cell(self, cell: bs4.Tag) -> str:
        """Parse a plain cell"""
        return cell.get_text(strip=True)

    def find_tag(self, tag: bs4.Tag, *args, **kwargs) -> bs4.Tag:
        """Wrapper for `Tag.find()`, mostly to appease pylint"""
        found = tag.find(*args, **kwargs)
        if not isinstance(found, bs4.Tag):
            raise WrongReplyError()
        return found

    def http_get(self, url, pos=0, stream=False) -> requests.Response:
        """Wrapper for `requests.get()`"""
        headers = {"User-Agent": self.USER_AGENT}
        if pos:
            headers["Range"] = f"bytes={pos}-"
        return requests.get(url, headers=headers, stream=stream, timeout=60)


if __name__ == "__main__":
    LibgenDownload().run()
