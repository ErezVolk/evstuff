#!/usr/bin/env -S uv run --script
"""Check some prices."""
import argparse
import difflib
import json
import time
from pathlib import Path

import requests
import rich.console
from fake_useragent import UserAgent  # ty: ignore[import-not-found]

THIS = Path(__file__)
HOUR = 60 * 60

PRE_MARKER = '"articleListsSettings":'
POST_MARKER = ',"filterSettings":'


class _SameDifferenceError(Exception):
    ...


def _get_browser_headers() -> dict[str, str]:
    ua = UserAgent()
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


def _parse_cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--url")
    parser.add_argument("-b", "--basename", type=Path, default=THIS)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-H", "--no-headers", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Check some prices."""
    args = _parse_cli()

    console = rich.console.Console()

    curr_time = time.time()
    url_path = args.basename.with_suffix(".url")
    html_path = args.basename.with_suffix(".html")
    report_path = args.basename.with_suffix(".report")

    if args.force:
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
        console.print("Writing", html_path)
        session = requests.Session()
        if not args.no_headers:
            session.headers.update(_get_browser_headers())

        url = args.url or url_path.read_text().strip()
        r = session.get(url)
        r.raise_for_status()

        html = r.text
        with html_path.open("wt") as fobj:
            fobj.write(html)

    pre_index = html.find(PRE_MARKER)
    post_index = html.find(POST_MARKER)
    if not 0 < pre_index < post_index:
        console.print("This is not what I expected")
        return

    articles = json.loads(html[pre_index + len(PRE_MARKER):post_index])["articles"]
    with html_path.with_suffix(".json").open("w") as fobj:
        json.dump(articles, fobj, ensure_ascii=False, indent=2)

    curr_lines = [
        (
            f"{a["manufacturer"]:<20} "
            f"{a["model"]:<40}"
            f"€ {int(float(a["price"]["primary"]["rawPrice"]))}"
            f"\n"
        )
        for a in articles
        if a["availability"]["isAvailable"]
    ]
    curr_report = "".join(curr_lines)
    try:
        prev_report = report_path.read_text()
        if prev_report == curr_report:
            raise _SameDifferenceError

        prev_lines = prev_report.splitlines(keepends=True)
        differ = difflib.Differ(charjunk=difflib.IS_CHARACTER_JUNK)
        delta = differ.compare(prev_lines, curr_lines)
        report = "".join(delta)
    except (FileNotFoundError, _SameDifferenceError):
        report = curr_report + "(Unchanged)"
    console.print(report.replace("B-Stock", "[r]B-Stock[/r]"))
    report_path.write_text(curr_report)


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.15"
# dependencies = ["requests", "fake_useragent", "rich"]
# ///
