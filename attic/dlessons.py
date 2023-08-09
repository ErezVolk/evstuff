#!/usr/bin/env python3
"""Download a bunch of lessons"""
import argparse
from dataclasses import dataclass
import datetime
from pathlib import Path
import subprocess
import time
import random
import shutil
import tempfile
import tomllib

import pandas as pd

HERE = Path.cwd()
THIS = Path(__file__)


@dataclass
class MainLesson:
    label: int
    mp4: Path
    jpg: Path
    new_mp4: Path | None = None


class DownloadLessons:
    """Download a bunch of lessons"""

    CONFIGURABLES = {
        "account_id": None,
        "embed_id": "default",
        "max_sleep": 5,
    }

    args: argparse.Namespace
    lsn: pd.DataFrame
    saves: int = 0

    def parse_args(self):
        """Command line"""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-t",
            "--table",
            type=Path,
            default="lessons.csv",
            help="where lesson IDs are stored",
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-n",
            "--number",
            type=int,
            default=1,
            help="number of lessons to download",
        )
        group.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="download all missing lessons",
        )
        group.add_argument(
            "-N",
            "--nop",
            action="store_true",
            help="just fill in missing file names in the CSV",
        )
        group.add_argument(
            "-p",
            "--push",
            nargs=3,
            type=int,
            metavar=("PART", "LESSON", "VIDEO_ID"),
            help="rename, insert lines, and all that (interactive)",
        )
        group.add_argument(
            "-v",
            "--video-id",
            nargs="+",
            type=int,
            help="Download specific VideoID(s) from the CSV",
        )
        group.add_argument(
            "-m",
            "--main-lesson",
            action="store_true",
            help="Try to rename downloaded lessons called 'Main Lesson'",
        )

        parser.add_argument("-s", "--max-sleep", metavar="SECONDS", type=int)
        parser.add_argument(
            "-o",
            "--order",
            choices=["recommended", "linear", "random"],
            default="recommended",
            help="how to choose which lessons to get",
        )
        parser.add_argument(
            "-c",
            "--config",
            type=Path,
            default=f"{THIS.stem}.toml",
            help="config file",
        )
        parser.add_argument("-A", "--account-id")
        parser.add_argument("-E", "--embed-id")
        self.args = parser.parse_args()

    def main(self):
        """Entry point"""
        self.parse_args()

        self.load_table()
        if not self.check_sanity():
            return
        if self.args.push:
            self.push()
        elif self.args.main_lesson:
            self.fix_main_lesson()
        elif self.args.nop:
            self.just_fill_in_things()
        elif self.args.video_id:
            self.download_specific_lessons()
        else:
            self.download_next_lessons()

    def load_table(self):
        """Read the CSV"""
        self.lsn = pd.read_csv(self.args.table)
        self.lsn.index = pd.RangeIndex(2, len(self.lsn) + 2)
        print(f"{self.args.table}: {self.desc()}")

    def check_sanity(self) -> bool:
        """Fill in some missing values and check some things"""
        if not self.lsn.VideoID.is_unique:
            lines = self.lsn.index[self.lsn.VideoID.duplicated(keep=False)]
            print("Duplicated VideoID in lines", ", ".join(map(str, lines)))
            return False

        if self.lsn.iloc[0].isna().Part:
            print("You must provide the first Part")
            return False
        # Fill in missing Part fields
        self.lsn.Part = self.lsn.Part.ffill().fillna(0).astype(int)

        # Make sure first Lesson in each Part is given
        parts = self.lsn.Part
        tmap = (parts != parts.shift(1)) & self.lsn.Lesson.isna()
        if tmap.sum() > 0:
            lines = self.lsn.index[tmap]
            print(
                "Missing first Lesson in Part in line(s)",
                ", ".join(map(str, lines)),
            )
            return False

        # Fill in missing Lesson fields
        deltas = self.lsn.groupby(self.lsn.Lesson.notna().cumsum()).cumcount()
        self.lsn.Lesson = (self.lsn.Lesson.ffill() + deltas).astype(int)

        # Fill in missing Done fields
        self.lsn.Done = self.lsn.Done.fillna(0).astype(int)
        return True

    def just_fill_in_things(self):
        """Nothing to download, look for unlisted downloaded files"""
        got = self.lsn[(self.lsn.Done == 1) & self.lsn.File.isna()]
        for label, row in got.iterrows():
            mnem = self.row_mnem(row)
            if name := self.get_name(mnem):
                print(f'{mnem} ({row.VideoID}) -> "{name}"')
                self.lsn.at[label, "File"] = name
        self.write()

    def download_specific_lessons(self):
        """CLI-provided VideoIDs"""
        wanted = self.args.video_id
        toget = self.lsn[self.lsn.VideoID.isin(wanted)]
        if len(toget) == 0:
            print(
                f"Not in {self.args.table}: "
                f"{' '.join(str(vid) for vid in wanted)}"
            )
            return

        if len(toget) < len(wanted):
            found = toget.VideoID
            missing = set(found) - set(wanted)
            print(
                f"Not in {self.args.table}: "
                f"{' '.join(str(vid) for vid in missing)}, "
                f"downloading only "
                f"{' '.join(str(vid) for vid in found)}, "
            )
            return

        self.download_lessons(toget)

    def download_next_lessons(self):
        """What we came here for"""
        toget = self.select()
        if len(toget) == 0:
            print("Nothing to download")
            return

        self.download_lessons(toget)

    def download_lessons(self, toget: pd.DataFrame):
        """Having figured out what to download, do it"""
        self.read_config()

        for label, row in toget.iloc[:-1].iterrows():
            self.download_lesson(label, row)
            self.sleep()
        self.download_lesson(toget.index[-1], toget.iloc[-1])

    def read_config(self):
        """Fill in settings from config file"""
        cfg = None

        for key, default in self.CONFIGURABLES.items():
            if getattr(self.args, key):
                continue

            if cfg is None:
                with open(self.args.config, "rb") as fobj:
                    cfg = tomllib.load(fobj)

            if default is None:
                value = cfg[key]
            else:
                value = cfg.get(key, default)
            setattr(self.args, key, value)

    def download_lesson(self, label, row):
        """Download a single lesson"""
        mnem = self.row_mnem(row)
        self.run_cli(
            "yt-dlp",
            f"http://players.brightcove.net/{self.args.account_id}/"
            f"{self.args.embed_id}_default/index.html?videoId={row.VideoID}",
            "-o",
            f"{mnem} %(title)s.%(ext)s",
        )
        self.lsn.at[label, "Done"] = 1
        if name := self.get_name(mnem):
            self.lsn.at[label, "File"] = name
        self.write()

    def run_cli(self, *cli):
        subprocess.run(cli, check=True)

    def push(self):
        """Insert lines, rename, etc."""
        (part, lesson, video_id) = self.args.push
        pushees = self.lsn.query(f"Part == {part} and Lesson >= {lesson}")
        if len(pushees) > 0:
            renames = {}
            for label, row in pushees[::-1].iterrows():
                old_mnem = self.mnem(part=row.Part, lesson=row.Lesson)
                new_mnem = self.mnem(part=row.Part, lesson=row.Lesson + 1)
                for src in HERE.glob(f"{old_mnem}*"):
                    renames[src] = dst = src.with_stem(
                        new_mnem + src.stem.removeprefix(old_mnem)
                    )
                    if row.File == src.name:
                        self.lsn.at[label, "File"] = dst.name
                self.lsn.at[label, "Lesson"] = row.Lesson + 1
            print(f"About to rename {len(renames)} file(s):")
            for src, dst in sorted(renames.items()):
                print(f"  '{src.name}' -> '{dst.name}'")
            input("Press Enter to continue...")
            for src, dst in sorted(renames.items(), reverse=True):
                src.rename(dst)

        addend = pd.DataFrame(
            columns=["VideoID", "Part", "Lesson", "Done"],
            data=[[video_id, part, lesson, 0]],
        )
        self.lsn = pd.concat([self.lsn, addend], ignore_index=True)
        self.lsn.sort_values(["Part", "Lesson"], inplace=True)
        self.write()

    def fix_main_lesson(self):
        """Look for lessons called 'Main Lesson'"""
        probs = self.lsn[self.mlsn_tmap()]
        if len(probs) == 0:
            print("There are no 'Main Lesson's.")
            return

        mlsns: list[MainLesson] = []
        with tempfile.TemporaryDirectory() as tdname:
            tdir = Path(tdname)
            for label, row in probs.iterrows():
                mp4 = Path(row.File)
                if not mp4.is_file():
                    print(f"{mp4} does not exist, cannot open")
                    continue
                jpg = tdir / f"{mp4.name}.jpg"
                self.run_cli(
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-ss",
                    "00:00:01",
                    "-i",
                    str(mp4),
                    "-frames:v",
                    "1",
                    str(jpg),
                )
                mlsns.append(MainLesson(label, mp4, jpg))
            self.run_cli("open", *[str(mlsn.jpg) for mlsn in mlsns])
            for mlsn in mlsns:
                new_name = input(f"New name for '{mlsn.mp4}'? ").strip()
                if not new_name:
                    continue
                mlsn.new_mp4 = mlsn.mp4.with_stem(
                    mlsn.mp4.stem.removesuffix("Main Lesson") + new_name
                )

        mlsns = [mlsn for mlsn in mlsns if mlsn.new_mp4]
        if not mlsns:
            return

        print("About to rename:")
        for mlsn in mlsns:
            print(f" - {mlsn.mp4} -> {mlsn.new_mp4}")
        input("Press Enter to continue: ")

        for mlsn in mlsns:
            assert mlsn.new_mp4 is not None  # Appease pyright
            self.lsn.at[mlsn.label, "File"] = str(mlsn.new_mp4)
            mlsn.mp4.rename(mlsn.new_mp4)
        self.write()

    def sleep(self):
        """Sleep as configured"""
        if not self.args.max_sleep:
            return
        seconds = random.random() * self.args.max_sleep
        print(f"[{self.now()}] Sleeping for {seconds:.02f} Sec...")
        time.sleep(seconds)

    def select(self) -> pd.DataFrame:
        """Figure out what to download"""
        undone = self.lsn[self.lsn.Done != 1]
        if len(undone) == 0:
            return undone

        if self.args.all:
            return undone

        if self.args.order == "random":
            return undone.sample(min(self.args.number, len(undone)))

        if self.args.order == "linear":
            return undone.iloc[: self.args.number]

        undone = undone.copy()
        part = self.lsn.Part
        undone["mid"] = (part == part.shift(1)) & (part == part.shift(-1))
        undone["line"] = undone.index
        undone.sort_values(["mid", "line"], inplace=True)
        return undone.iloc[: self.args.number]

    def row_mnem(self, row: pd.Series) -> str:
        """A lesson's mnemonic"""
        return self.mnem(row.Part, row.Lesson)

    def mnem(self, part, lesson) -> str:
        """A lesson's mnemonic"""
        return f"{int(part)}.{int(lesson):02d}"

    def get_name(self, mnem: str) -> str | None:
        """Find video file matching a lesson"""
        names = [path.name for path in HERE.glob(f"{mnem} *.mp4")]
        if len(names) == 1:
            return names[0]
        return None

    def mlsn_tmap(self) -> pd.Series:
        """Return Truth map of files called 'Main Lesson'."""
        names = self.lsn.File.astype("string").str
        return names.fullmatch(r"\d\.\d+ Main Lesson\.mp4")

    def write(self):
        """Write back the csv"""
        if self.saves == 0:
            backup = self.args.table.with_suffix(".bak")
            print(f"{self.args.table} -> {backup}")
            shutil.copy(self.args.table, backup)

        print(f"Writing {self.args.table} ({self.desc()})")
        self.lsn.to_csv(self.args.table, index=False)
        self.saves = self.saves + 1

        if self.mlsn_tmap().sum() > 0:
            print("You may want to run with --main-lesson")

    def desc(self) -> str:
        """Description of number of lines and number done"""
        n_done = self.lsn.Done.sum()
        n_all = len(self.lsn)
        return f"{n_all} line(s), {int(n_done)} done"

    def now(self):
        """The time"""
        return datetime.datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    DownloadLessons().main()
