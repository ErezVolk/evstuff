#!/usr/bin/env python3
"""Download a bunch of lessons"""
import argparse
from pathlib import Path
import subprocess
import time
import random
import shutil
import tomllib

import pandas as pd


class DownloadLessons:
    """Download a bunch of lessons"""

    args: argparse.Namespace
    saves: int = 0

    def parse_args(self):
        """Command line"""
        parser = argparse.ArgumentParser()
        parser.add_argument("--table", "-t", type=Path, default="lessons.csv")
        parser.add_argument("--number", "-n", type=int, default=1)
        parser.add_argument("--max-sleep", "-m", metavar="SECONDS", type=int)
        parser.add_argument("--reverse", "-r", action="store_true")
        parser.add_argument(
            "--config", "-c", type=Path, default=f"{Path(__file__).stem}.toml"
        )
        self.args = parser.parse_args()

    def main(self):
        """Entry point"""
        self.parse_args()

        lessons = pd.read_csv(self.args.table)
        print(f"{self.args.table}: {len(lessons)} lines")

        if not lessons.VideoID.is_unique:
            lines = lessons.index[lessons.VideoID.duplicated(keep=False)] + 2
            print("Duplicated VideoID in lines", ", ".join(map(str, lines)))
            return

        if lessons.iloc[0].isna().Part:
            print("You must provide the first Part")
            return
        lessons.Part = lessons.Part.ffill().fillna(0).astype(int)

        tmap = (lessons.Part != lessons.Part.shift(1)) & lessons.Lesson.isna()
        if tmap.sum() > 0:
            lines = lessons.index[tmap] + 2
            print("Missing first Lesson in Part in line(s)", ", ".join(map(str, lines)))
            return
        return
        deltas = lessons.groupby(lessons.Lesson.notna().cumsum()).cumcount()
        lessons.Lesson = (lessons.Lesson.ffill() + deltas).astype(int)

        lessons.Done = lessons.Done.fillna(0).astype(int)

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
            if self.args.max_sleep is None:
                self.args.max_sleep = cfg.get("max_sleep", 5)

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
        if self.saves == 0:
            backup = self.args.table.with_suffix(".bak")
            print(f"{self.args.table} -> {backup}")
            shutil.copy(self.args.table, backup)

        print(f"Writing {self.args.table}")
        lessons.to_csv(self.args.table, index=False)
        self.saves = self.saves + 1


if __name__ == "__main__":
    DownloadLessons().main()
