#!/usr/bin/env -S uv run --script
"""Split album."""
import re
import shlex
import subprocess
import tomllib
from pathlib import Path

import pandas as pd  # ty: ignore[unresolved-import]
import unidecode  # ty: ignore[unresolved-import]

TRACK_EXPRS = (
    r"(?P<time>[0-9:]+) (?P<title>\S.*\S)",
)


__TODO__ = """
- Other formats
- The ones with lengths
- No commas in names
- Track count? Using id3v2 if available?
- Check for mp3splt
- Take URL, call yt-dlp
"""


def split_album() -> None:
    """Split album."""
    with Path("album.toml").open("rb") as fobj:
        info = tomllib.load(fobj)

    whole = info["whole"]
    artist = info["artist"]
    album = info["album"]
    year = info["year"]
    genre = info.get("genre", 8)

    track_desc = unidecode.unidecode(info["tracks"])
    track_lines = [
        meat
        for line in track_desc.split("\n")
        if (meat := line.strip())
    ]
    for expr in TRACK_EXPRS:
        mobjs = [re.fullmatch(expr, line) for line in track_lines]
        if all(mobj is not None for mobj in mobjs):
            break
    else:
        print("Don't know how to interpret these tracks.")
        return

    tracks = pd.DataFrame([
        mobj.groupdict() for mobj in mobjs if mobj is not None
    ])
    tracks["time"] = tracks.time.str.replace(
        ":", ".", regex=False
    ).replace(
        r"^0+\.([0-9]+\.[0-9]+)", r"\1", regex=True
    ).replace(
        r"^0+(\d)", r"\1", regex=True
    )

    # Youtube comment is START TIMES
    tracks["start"] = tracks.time
    tracks["stop"] = tracks.time.shift(-1, fill_value="EOF")
    tracks.loc[0, "start"] = "0.00"

    tracks["number"] = tracks.index + 1

    folder = f"{artist} - {album}"
    common_tags = f"@a={artist},@b={album},@y={year},@g={genre}"
    cmds = [
        [
            "mp3splt",
            "-o", f"{folder}/{row.number} - {row.title}",
            "-g", f"[{common_tags},@t={row.title},@n={row.number}]",
            whole, row.start, row.stop,
        ]
        for _, row in tracks.iterrows()
    ]
    for cmd in cmds:
        print(" ".join(map(shlex.quote, cmd)))
    input("Press Enter to run...")
    for cmd in cmds:
        subprocess.run(cmd, check=True)
    subprocess.run(["/usr/bin/open", folder], check=False)


if __name__ == "__main__":
    split_album()

# /// script
# dependencies = ["unidecode", "pandas"]
# ///
