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
    df: pd.DataFrame
    saves: int = 0

    def parse_args(self):
        """Command line"""
        parser = argparse.ArgumentParser()
        parser.add_argument("-t", "--table", type=Path, default="lessons.csv")
        parser.add_argument("-n", "--number", type=int, default=1)
        parser.add_argument("-s", "--max-sleep", metavar="SECONDS", type=int)
        parser.add_argument(
            "-o",
            "--order",
            choices=["recommended", "linear", "random"],
            default="recommended",
        )
        parser.add_argument(
            "--config", "-c", type=Path, default=f"{Path(__file__).stem}.toml"
        )
        self.args = parser.parse_args()

    def main(self):
        """Entry point"""
        self.parse_args()

        self.load_table()
        if not self.check_sanity():
            return
        if self.args.number == 0:
            self.just_fill_in_things()
        else:
            self.download_lessons()

    def load_table(self):
        """Read the CSV"""
        self.df = pd.read_csv(self.args.table)
        self.df.index = pd.RangeIndex(2, len(self.df) + 2)
        print(f"{self.args.table}: {len(self.df)} lines")

    def check_sanity(self) -> bool:
        """Fill in some missing values and check some things"""
        if not self.df.VideoID.is_unique:
            lines = self.df.index[self.df.VideoID.duplicated(keep=False)]
            print("Duplicated VideoID in lines", ", ".join(map(str, lines)))
            return False

        if self.df.iloc[0].isna().Part:
            print("You must provide the first Part")
            return False
        self.df.Part = self.df.Part.ffill().fillna(0).astype(int)

        tmap = (self.df.Part != self.df.Part.shift(1)) & self.df.Lesson.isna()
        if tmap.sum() > 0:
            lines = self.df.index[tmap]
            print(
                "Missing first Lesson in Part in line(s)",
                ", ".join(map(str, lines)),
            )
            return False

        deltas = self.df.groupby(self.df.Lesson.notna().cumsum()).cumcount()
        self.df.Lesson = (self.df.Lesson.ffill() + deltas).astype(int)

        self.df.Done = self.df.Done.fillna(0).astype(int)
        return True

    def just_fill_in_things(self):
        """Nothing to download, look for unlisted downloaded files"""
        got = self.df[(self.df.Done == 1) & self.df.File.isna()]
        for label, row in got.iterrows():
            mnem = self.mnem(row)
            if (name := self.get_name(mnem)):
                print(f'{mnem} ({row.VideoID}) -> "{name}"')
                self.df.at[label, "File"] = name
        self.write()

    def download_lessons(self):
        """What we came here for"""
        undone = self.df[self.df.Done != 1]
        if len(undone) == 0:
            print("Nothing to download")
            return

        match self.args.order:
            case "random":
                toget = undone.sample(min(self.args.number, len(undone)))

            case "linear":
                toget = undone.iloc[: self.args.number]

            case _:
                undone = undone.copy()
                undone["unlast"] = self.df.Part == self.df.Part.shift(-1)
                undone["line"] = undone.index
                undone.sort_values(["unlast", "line"], inplace=True)
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
            self.df.at[label, "Done"] = 1
            if (name := self.get_name(mnem)):
                self.df.at[label, "File"] = name
            self.write()
            if mnem != mnems[-1]:
                if self.args.max_sleep:
                    seconds = random.random() * self.args.max_sleep
                    print(f"Sleeping for {seconds:.02f} Sec...")
                    time.sleep(seconds)

    def mnem(self, row: pd.Series) -> str:
        """A lesson's mnemonic"""
        return f"{int(row.Part)}.{int(row.Lesson):02d}"

    def get_name(self, mnem: str) -> str | None:
        """Find video file matching a lesson"""
        names = [path.name for path in Path.cwd().glob(f"{mnem} *.mp4")]
        if len(names) == 1:
            return names[0]
        return None

    def write(self):
        """Write back the csv"""
        if self.saves == 0:
            backup = self.args.table.with_suffix(".bak")
            print(f"{self.args.table} -> {backup}")
            shutil.copy(self.args.table, backup)

        n_done = self.df.Done.sum()
        n_all = len(self.df)
        print(f"Writing {self.args.table} (done: {n_done} of {n_all})")
        self.df.to_csv(self.args.table, index=False)
        self.saves = self.saves + 1


if __name__ == "__main__":
    DownloadLessons().main()
