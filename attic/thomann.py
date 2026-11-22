#!/usr/bin/env -S uv run --script
import difflib
import json
import sys
import time
from pathlib import Path

import requests
from fake_useragent import UserAgent  # ty: ignore[import-not-found]

THIS = Path(__file__)
HOUR = 60 * 60

PRE_MARKER = '"articleListsSettings":'
POST_MARKER = ',"filterSettings":'


class SameDifference(Exception):
    ...


def get_browser_headers():
    ua = UserAgent()
    return {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }



def main():
    curr_time = time.time()
    url_path = THIS.with_suffix(".url")
    html_path = THIS.with_suffix(".html")
    report_path = THIS.with_suffix(".report")

    try:
        prev_time = html_path.stat().st_mtime
    except FileNotFoundError:
        prev_time = curr_time

    if prev_time > curr_time - (4 * HOUR):
        html = html_path.read_text()
    else:
        print("Writing", html_path)
        session = requests.Session()
        session.headers.update(get_browser_headers())

        url = url_path.read_text().strip()
        r = session.get(url)
        r.raise_for_status()

        html = html_path.read_text()
        with html_path.open("wt") as fobj:
            fobj.write(r.text)

    pre_index = html.find(PRE_MARKER)
    post_index = html.find(POST_MARKER)
    if not 0 < pre_index < post_index:
        print("This is not what I expected")
        return

    articles = json.loads(html[pre_index + len(PRE_MARKER):post_index])["articles"]
    with html_path.with_suffix(".json").open("w") as fobj:
        json.dump(articles, fobj, ensure_ascii=False, indent=2)

    curr_lines = [
        f"{a["model"]:<40}€ {int(float(a["price"]["primary"]["rawPrice"]))}\n"
        for a in articles
        if a["availability"]["isAvailable"]
    ]
    curr_report = "".join(curr_lines)
    try:
        prev_report = report_path.read_text()
        if prev_report == curr_report:
            raise SameDifference

        prev_lines = prev_report.splitlines(keepends=True)
        differ = difflib.Differ(charjunk=difflib.IS_CHARACTER_JUNK)
        delta = differ.compare(prev_lines, curr_lines)
        report = "".join(delta)
    except (FileNotFoundError, SameDifference):
        report = curr_report
        pass
    print(report)
    report_path.write_text(curr_report)


if __name__ == "__main__":
    main()

# /// script
# requires-python = ">=3.15"
# dependencies = ["requests", "fake_useragent"]
# ///
