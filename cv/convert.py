#!/usr/bin/env python3
"""Create translation CVs"""
import argparse
from pathlib import Path
import re
import sys

from docxtpl import DocxTemplate
import pandas as pd

HERE = Path.cwd().resolve()
THIS = Path(__file__).resolve()


class ConvertCV:
    """Create translation CVs"""
    parser: argparse.ArgumentParser
    args: argparse.Namespace
    works: pd.DataFrame
    pub_lat: dict[str, str]
    lgs: pd.DataFrame
    latin_langs: set[str]

    def parse_args(self):
        """Usage of this script"""
        known_lgs = [
            match.group(1)
            for path in HERE.iterdir()
            if (match := re.match(r"erez-volk-cv-(..)-tpl\.docx$", path.name))
        ]

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-l",
            "--langs",
            metavar="LANG",
            nargs="+",
            default=known_lgs,
            help=f"Languages [{' '.join(known_lgs)}]",
        )
        self.args = parser.parse_args()
        self.parser = parser

    def run(self):
        """The main function"""
        self.parse_args()
        self.read_tables()

        for lang in self.args.langs:
            self.convert_to(lang)

    def read_tables(self):
        """Read the lists of works, publishers, etc."""
        self.works = self.read_tsv("works")
        self.works["is_book"] = self.works.in_he == ""
        pubs = self.read_tsv("publishers")
        self.lgs = self.read_tsv("lgs").set_index("lg")

        # Works in an unknown language
        self.latin_langs = set(self.lgs.query("script == 'latin'").index)
        langs = set(self.lgs.index)
        bad_lgs = set(self.works.lg.unique()) - langs
        if bad_lgs:
            self.die(
                f"Unknown language code(s): "
                f"{' '.join(map(repr, bad_lgs))}"
            )

        # Works with an unknown publisher
        work_pubs = self.works.publisher_he.unique()
        known_pubs = pubs.publisher_he
        bad_pubs = set(work_pubs) - set(known_pubs)
        if bad_pubs:
            self.die(f"Unknown publisher(s): {' '.join(map(repr, bad_pubs))}")
        self.pub_lat = {
            row.publisher_he: row.publisher_lat for _, row in pubs.iterrows()
        }

        # Works without the bare minimum
        tmap = (
            self.works[["author_he", "title_he", "author_lat", "year"]]
            .isna()
            .any(axis=1)
        )
        if tmap.sum() > 0:
            self.die(
                f"Missing Hebrew author/title on works.tsv:"
                f"{',':join(map(str(self.works.index[tmap])))}"
            )

        # Works with no title in the original language
        for lang in langs:
            self.works.loc[self.works.lg == lang, "title_orig"] = self.works[
                f"title_{lang}"
            ]
        tmap = self.works.title_orig.isna()
        if tmap.sum() > 0:
            bad = self.works[tmap].title_he
            self.die(f"Missing original titles(s): {' '.join(map(repr, bad))}")

    def die(self, msg: str):
        """Print error message and quit"""
        print(msg)
        sys.exit(-1)

    def convert_to(self, lang: str):
        """Generate CV for a single language"""
        if lang == "he":
            raise NotImplementedError("Convert to Hebrew")

        path = Path(f"erez-volk-cv-{lang}.docx")
        print(f"Creating {path}...")

        l10n = self.lgs.loc[lang]

        orig_map = {
            orig: row[f"lg_{lang}"]
            for orig, row in self.lgs.iterrows()
        }
        frame = pd.DataFrame(
            {
                "language": self.works.lg.map(orig_map),
                "year": self.works.year,
                "author": self.works.author_lat,
                "is_book": self.works.is_book,
                "in_work": self.works.in_lat,
            }
        )

        try:
            author_lang = self.works[f"author_{lang}"]
            frame.loc[author_lang != "", "author"] = author_lang
        except KeyError:
            pass

        # Multi-author works
        tmap = frame.author.str.contains(",")
        l10n_and = f" {l10n.l10n_and} "
        frame.loc[tmap, "author"] = frame[tmap].author.str.replace(
            r",\s*", l10n_and, regex=True
        )

        # Make sure all works have a title in this language
        title = self.works[f"title_{lang}"]
        tmap = title.isna()
        if tmap.sum() > 0:
            bad = self.works[tmap].title_he
            self.die(f"Missing {lang} titles(s): {' '.join(map(repr, bad))}")

        # Add the original title when not this language
        self.works["title"] = title
        frame["title"] = title
        tmap = self.works.lg != lang
        tmap &= self.works.title != self.works.title_orig
        tmap &= self.works.lg.isin(self.latin_langs)
        frame.loc[tmap, "title"] = self.works[tmap].apply(
            lambda row: f"{row.title_orig} [{row.title}]", axis=1
        )

        # Publisher's name
        frame["publisher"] = self.works.publisher_he.map(self.pub_lat)

        # Sort and leave language only on first book of each
        frame.sort_values(
            ["language", "year"],
            inplace=True,
        )
        frame["n"] = frame.title.notna().cumsum()

        # Just for debugging
        frame.to_csv(f"{path}.csv", index=False)

        # Now the template:
        tpl = DocxTemplate(path.with_stem(path.stem + "-tpl"))
        tpl.render(
            {
                "sections": [
                    {
                        "language": language,
                        "works": [
                            {col: work[col] for col in frame.columns}
                            for _, work in group.iterrows()
                        ],
                    }
                    for language, group in frame.groupby("language")
                ]
            }
        )
        tpl.save(path)

        # And a rerun script
        rerun = Path(f"{path}.rerun")
        with open(rerun, "wt", encoding="ascii") as fobj:
            fobj.write(
                f"#!/bin/sh\n"
                f"cd {HERE}\n"
                f"/usr/local/bin/python3 {THIS} -l {lang}\n"
            )
        rerun.chmod(0o755)

    def read_tsv(self, stem: str) -> pd.DataFrame:
        """Read tab-separated values and strip whitespace"""
        path = f"{stem}.tsv"
        frame = pd.read_csv(path, sep="\t")
        print(f"Reading {path}: n = {len(frame)}")
        frame.index.name = "line"
        frame.index = frame.index + 2
        for col, dtype in zip(frame.columns, frame.dtypes):
            if pd.api.types.is_string_dtype(dtype):
                frame[col] = frame[col].fillna("").str.strip()
        return frame


if __name__ == "__main__":
    ConvertCV().run()
