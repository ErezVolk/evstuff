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

NOT_COMMA = "_"
COVER_TAG = "APIC:Album cover"


__TODO__ = """
- Other formats
- The ones with lengths
- Check for mp3splt/yt-dlp
- lines from mp3 (`mutagen.file(path)["TXXX:description"].text[0].split("\n")`)
  - But should ignore other lines.
"""


class SplitAlbum:
    """Split album."""

    def run(self) -> None:
        """Split album."""
        with Path("album.toml").open("rb") as fobj:
            info = tomllib.load(fobj)

        whole = Path(self._get_whole(info))
        if not whole.is_file():
            self._fail(f"File not found: {whole}")

        artist = info["artist"]
        album = info["album"].replace(",", NOT_COMMA)
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
        tracks["title"] = tracks.title.str.replace(",", NOT_COMMA, regex=False)

        # Youtube comment is START TIMES
        tracks["start"] = tracks.time
        tracks["stop"] = tracks.time.shift(-1, fill_value="EOF")
        tracks.loc[0, "start"] = "0.00"

        tracks["number"] = tracks.index + 1

        folder = Path(f"{artist} - {album}")
        tracks["stem"] = tracks.number.astype(str) + " - " + tracks.title

        common_tags = f"@a={artist},@b={album},@y={year},@g={genre}"
        cmds = [
            [
                "mp3splt",
                "-d", folder,
                "-o", row.stem,
                "-g", f"[{common_tags},@t={row.title},@n={row.number}]",
                whole, row.start, row.stop,
            ]
            for _, row in tracks.iterrows()
        ]
        for cmd in cmds:
            print(" ".join(map(shlex.quote, map(str, cmd))))
        input("Press Enter to run...")
        for cmd in cmds:
            subprocess.run(cmd, check=True)
        self._extract_cover(whole, folder)
        self._try_id3v2(folder, tracks)

        subprocess.run(["/usr/bin/open", folder], check=False)

    def _fail(self, message: str) -> t.Never:
        print(message)
        sys.exit()

    def _get_whole(self, info: dict) -> str:
        if not (url := info.get("url")):
            return info["whole"]
        cmd = [
            "yt-dlp",
            "-t", "mp3",
            "--print", "filename",
            "--embed-thumbnail", "--embed-metadata",
            "--no-playlist",
            url
        ]
        print(" ".join(cmd))
        proc = subprocess.run(cmd, check=True, capture_output=True, encoding="utf-8")
        whole = Path(proc.stdout.strip())
        if not whole.is_file():
            if not (whole := whole.with_suffix(".mp3")).is_file():
                raise RuntimeError("Can't find downloaded file")
        print(f"Downloaded {whole}")
        return str(whole)

    def _extract_cover(self, mp3: Path, folder: Path) -> None:
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

    def _try_id3v2(self, folder: Path, tracks: pd.DataFrame) -> None:
        cmds = [
            [
                "id3v2",
                "-T", f"{row.number}/{len(tracks)}",
                folder / f"{row.stem}.mp3",
            ]
            for _, row in tracks.iterrows()
        ]
        for cmd in cmds:
            proc = subprocess.run(cmd, check=False)
            if proc.returncode != 0:
                return


if __name__ == "__main__":
    SplitAlbum().run()

# /// script
# dependencies = ["unidecode", "pandas", "mutagen"]
# ///
