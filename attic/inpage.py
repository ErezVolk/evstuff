#!/usr/bin/env -S uv run --script
"""Get a page, look for a substring."""
import argparse
import time
import tomllib
from pathlib import Path

import requests
import rich.console

THIS = Path(__file__)
HOUR = 60 * 60
MAX_URL = 40


class InPage:
    """Get a page, look for a substring."""

    parser: argparse.ArgumentParser
    args: argparse.Namespace
    cfg: dict | None = None

    def _parse_cli(self) -> None:
        self.parser = parser = argparse.ArgumentParser()
        parser.add_argument(
            "-c", "--config", default=THIS.with_suffix(".toml"), type=Path,
        )
        parser.add_argument("-f", "--force", action="store_true")
        parser.add_argument("-u", "--url")
        parser.add_argument("-n", "--needle")
        self.args = parser.parse_args()

    def _get(self, key: str) -> str:
        """Lazy TOML read of config file."""
        if self.cfg is None:
            with self.args.config.open("rb") as fobj:
                self.cfg = tomllib.load(fobj)
        return self.cfg[key]

    def main(self) -> None:
        """Check some prices."""
        self._parse_cli()

        console = rich.console.Console()

        try:
            url = self.args.url or self._get("url")
        except KeyError:
            self.parser.error(
                f"Supply a URL, either via --url or in {self.args.config}"
            )

        try:
            needle = self.args.needle or self._get("needle")
        except KeyError:
            self.parser.error(
                f"Supply a substring, either via --needle or in {self.args.config}"
            )

        curr_time = time.time()
        html_path = self.args.config.with_suffix(".html")

        if self.args.force:
            should_get = True
        else:
            try:
                prev_time = html_path.stat().st_mtime
                should_get = curr_time >= prev_time + (4 * HOUR)
            except FileNotFoundError:
                should_get = True

        if not should_get:
            html = html_path.read_text()
        else:
            session = requests.Session()
            r = session.get(url.strip())
            r.raise_for_status()

            html = r.text
            html_path.write_text(html)

        found = needle in html
        stub = url if len(url) < MAX_URL else f"{url[:MAX_URL]}…"
        console.print(
            f"{needle!r} [b]{'FOUND' if found else 'NOT found'}[/b] in {stub}"
        )


if __name__ == "__main__":
    InPage().main()

# /// script
# requires-python = ">=3.15"
# dependencies = ["requests", "rich"]
# ///
