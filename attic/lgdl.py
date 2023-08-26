#!/usr/bin/env python3
"""Search and download from libgen"""
import argparse
from pathlib import Path
import typing as t
import urllib.parse

import bs4
import requests
from simple_term_menu import TerminalMenu
from tqdm import tqdm


class Hit(t.NamedTuple):
    """A query result"""
    name: str
    language: str
    size_desc: str
    mirror: str


class LibgenDownload:
    """Simple Library Genesis search + download"""
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "QtWebEngine/5.15.5 "
        "Chrome/87.0.4280.144 "
        "Safari/537.36"
    )
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
        hits.sort(key=lambda hit: hit.name.lower())
        choices = self.choose(hits)
        if not choices:
            print("Better luck next time!")
            return
        for choice in choices:
            self.download(hits[choice])

    def run_query(self) -> list[Hit]:
        """Search LibGen and grok the result"""
        if self.args.reload:
            with open("lgdl-query.html", encoding="utf-8") as fobj:
                html = fobj.read()
        else:
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

        # Parse query results
        soup = bs4.BeautifulSoup(html, "html.parser")
        table = self.find_tag(soup, "table", id="tablelibgen")

        columns = [
            next(col.strings).strip()
            for col in self.find_tag(table, "thead").find_all("th")
        ]
        hits = [
            self.parse_row(row, columns)
            for row in self.find_tag(table, "tbody").find_all("tr")
        ]
        return [
            hit for hit in hits
            if hit.mirror  # Only what we can actually download
        ]

    def choose(self, hits: list[Hit]) -> list[int]:
        """Ask the user what to download"""
        menu = TerminalMenu(
            [
                f"{hit.name} ({hit.language}, {hit.size_desc})"
                for hit in hits
            ],
            multi_select=True,
            show_multi_select_hint=True,
        )
        return menu.show()

    def download(self, hit: Hit):
        """Download one file"""
        final_path = self.args.output / hit.name
        if final_path.is_file():
            print(f"File already exists: {final_path}")
            return

        print(f"{hit.name} ({hit.size_desc})", flush=True)
        url = self.read_mirror(hit.mirror)

        # Are we continuing?
        work_path = self.args.output / "f{hit.name}.lgdl"
        if work_path.is_file():
            pos = work_path.stat().st_size
            mode = "ab"
            if self.args.debug:
                print(f"Resume download at {pos:,} B...")
        else:
            self.args.output.mkdir(parents=True, exist_ok=True)
            pos = 0
            mode = "wb"

        # Read the actual thng
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
        work_path.rename(final_path)

        progress.close()

    def read_mirror(self, mirror_url: str) -> str:
        """Read LibGen mirror page, return download URL"""
        response = self.http_get(mirror_url)
        mirror_html = response.text
        if self.args.debug:
            with open("lgdl-mirror.html", "w", encoding="utf-8") as fobj:
                fobj.write(mirror_html)
        soup = bs4.BeautifulSoup(mirror_html, "html.parser")
        href = self.find_tag(soup, "a", string="GET")["href"]
        assert isinstance(href, str)
        return urllib.parse.urljoin(mirror_url, href)

    def parse_row(self, row: bs4.Tag, columns: list[str]) -> Hit:
        """Convert a query table row to a dict"""
        if self.args.debug:
            print("Get URL...", flush=True)
        fields = {
            column: self.parse_cell(column, cell)
            for column, cell in zip(columns, row.find_all("td"))
        }
        name = fields["ID"].strip(" .")

        author = fields["Author(s)"]
        if author == "coll.":
            author = None
        if not author and ": " in name:
            author, name = name.split(": ", 1)
        if author:
            author = author.split(",", 1)[0]
            author = author.split(";", 1)[0]
            author = author.strip()
            name = f"{author} - {name}"

        if (ext := fields["Ext."]):
            name = f"{name}.{ext}"

        return Hit(
            name=name,
            language=fields["Language"],
            size_desc=fields["Size"],
            mirror=fields["Mirrors"],
        )

    def parse_cell(self, column: str, cell: bs4.Tag) -> str:
        """Get the interesting bits"""
        if column == "ID":  # The title and stuff
            for link in cell.find_all("a"):
                text = link.get_text(strip=True)
                if text:
                    return text
        if column == "Mirrors":
            for link in cell.find_all("a"):
                href = link["href"]
                if isinstance(href, str):
                    return href
            return ""
        return cell.get_text(strip=True)

    def find_tag(self, tag: bs4.Tag, *args, **kwargs) -> bs4.Tag:
        """Wrapper for `Tag.find()`, mostly to appease pylint"""
        found = tag.find(*args, **kwargs)
        assert isinstance(found, bs4.Tag)
        return found

    def http_get(
        self,
        url,
        pos=0,
        stream=False,
        timeout=60
    ) -> requests.Response:
        """Wrapper for `requests.get()`"""
        headers = {"User-Agent": self.USER_AGENT}
        if pos:
            headers["Range"] = f"bytes={pos}-"
        return requests.get(
            url,
            headers=headers,
            stream=stream,
            timeout=timeout,
        )


if __name__ == "__main__":
    LibgenDownload().run()
