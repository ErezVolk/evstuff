#!/usr/bin/env python3
"""Download a bunch of lessons"""
import argparse
from pathlib import Path
import subprocess
import time
import random
import tomllib

import pandas as pd


class DownloadLessons:
    """Download a bunch of lessons"""

    args: argparse.Namespace

    def parse_args(self):
        """Command line"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--table", "-t", type=Path, default="lessons.csv")
        parser.add_argument("--number", "-n", type=int, default=1)
        parser.add_argument("--max-sleep", "-m", metavar="SECONDS", type=int, default=5)
        parser.add_argument("--reverse", "-r", action="store_true")
        parser.add_argument(
            "--config", "-c", type=Path, default=f"{Path(__file__).stem}.toml"
        )
        self.args = parser.parse_args()

    def main(self):
        """Entry point"""
        self.parse_args()

        lessons = pd.read_csv(self.args.table)

        if not lessons.VideoID.is_unique:
            lines = lessons.index[lessons.VideoID.duplicated(keep=False)] + 2
            print("Duplicated VideoID in lines", ", ".join(map(str, lines)))
            return

        lessons.Done = lessons.Done.fillna(0).astype(int)
        lessons.Part = lessons.Part.ffill().astype(int)
        deltas = lessons.groupby(lessons.Lesson.notna().cumsum()).cumcount()
        lessons.Lesson = (lessons.Lesson.ffill() + deltas).astype(int)

        if self.args.number == 0:
            # Just fill in things
            got = lessons[(lessons.Done == 1) & lessons.File.isna()]
            for label, row in got.iterrows():
                mnem = self.mnem(row)
                if (name := self.get_name(mnem)):
                    print(f'{mnem} ({row.VideoID}) -> "{name}"')
                    lessons.at[label, "File"] = name
            self.write(lessons)
            return

        undone = lessons[lessons.Done != 1]
        if len(undone) == 0:
            print("Nothing to download")
            return
        if self.args.reverse:
            undone = undone.iloc[::-1]
        toget = undone.iloc[: self.args.number]

        with open(self.args.config, "rb") as fobj:
            cfg = tomllib.load(fobj)
            account_id = cfg["account_id"]
            embed_id = cfg.get("embed_id", "default")

        mnems = [self.mnem(row) for _, row in toget.iterrows()]

        for mnem, (label, row) in zip(mnems, toget.iterrows()):
            subprocess.run(
                [
                    "yt-dlp",
                    f"http://players.brightcove.net/{account_id}/"
                    f"{embed_id}_default/index.html?videoId={row.VideoID}",
                    "-o",
                    f"{mnem} %(title)s.%(ext)s",
                ],
                check=True,
            )
            lessons.at[label, "Done"] = 1
            if (name := self.get_name(mnem)):
                lessons.at[label, "File"] = name
            self.write(lessons)
            if mnem != mnems[-1]:
                if self.args.max_sleep:
                    seconds = random.random() * self.args.max_sleep
                    print(f"Sleeping for {seconds:.02f} Sec...")
                    time.sleep(seconds)

    def mnem(self, row) -> str:
        """A lesson's mnemonic"""
        return f"{int(row.Part)}.{int(row.Lesson):02d}"

    def get_name(self, mnem) -> str | None:
        """Find video file matching a lesson"""
        names = [path.name for path in Path.cwd().glob(f"{mnem} *.mp4")]
        if len(names) == 1:
            return names[0]
        return None

    def write(self, lessons: pd.DataFrame):
        """Write back the csv"""
        print(f"Writing {self.args.table}")
        lessons.to_csv(self.args.table, index=False)


if __name__ == "__main__":
    DownloadLessons().main()
