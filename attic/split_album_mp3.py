#!/usr/bin/env -S uv run --script
# ty: ignore[unresolved-import]
"""Split album."""
import mimetypes
import re
import shlex
import subprocess
import sys
import tomllib
import typing as t
from pathlib import Path

import mutagen
import pandas as pd
import unidecode

TRACK_EXPRS = (
    r"(?P<time>[0-9:]+) (?P<title>\S.*\S)",
)

COVER_TAG = "APIC:Album cover"


__TODO__ = """
- Other formats
- The ones with lengths
- No commas in names
- Track count? Using id3v2 if available?
- Check for mp3splt
- Take URL, call yt-dlp --print filename
- Split from mp3 (`mutagen.file(path)["TXXX:description"].text[0].split("\n")`)
"""


class SplitAlbum:
    """Split album."""

    def run(self) -> None:
        """Split album."""
        with Path("album.toml").open("rb") as fobj:
            info = tomllib.load(fobj)

        whole = info["whole"]
        if not Path(whole).is_file():
            self._fail(f"File not found: {whole}")

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
            self._fail("Don't know how to interpret these tracks.")

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
        self._extract_cover(whole, folder)

        subprocess.run(["/usr/bin/open", folder], check=False)

    def _fail(self, message: str) -> t.Never:
        print(message)
        sys.exit()

    def _extract_cover(self, mp3: str, folder: str) -> None:
        try:
            mut = mutagen.File(mp3)
            cover = mut[COVER_TAG]
            ext = mimetypes.guess_extension(cover.mime)
            if not ext:
                raise ValueError(f"Unknown mime type {cover.mime}")
            path = Path(folder) / f"cover{ext}"
            path.write_bytes(cover.data)
            print(f"Wrote {path} ({path.stat().st_size:,} bytes)")
        except (mutagen.MutagenError, ValueError) as exc:
            print(f"Cannot extract cover: {exc}")
        except KeyError:
            print("Cannot extract cover: No cover")


if __name__ == "__main__":
    SplitAlbum().run()

# /// script
# dependencies = ["unidecode", "pandas", "mutagen"]
# ///
