#!/usr/bin/env python3
"""Shuffle paragraphs in a Word document"""
import argparse
from collections import defaultdict
from pathlib import Path
import pickle
import random
import re

from lxml import etree
import numpy as np

from docx_worker import DocxWorker


class DocxShuffle(DocxWorker):
    """Shuffle paragraphs in a Word document"""
    args: argparse.Namespace
    body: etree._Entity
    rng: np.random.Generator

    def parse_args(self):
        """Command-line options"""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "input",
            type=Path,
            nargs="?",
        )
        parser.add_argument(
            "-m",
            "--model",
            type=Path,
        )
        parser.add_argument(
            "-s",
            "--stem",
            type=Path,
        )
        parser.add_argument(
            "-S",
            "--one-time-seed",
            action="store_true",
        )
        parser.add_argument(
            "-c",
            "--contains",
            metavar="REGEX",
        )
        self.args = parser.parse_args()
        if self.args.input is None:
            docs = self.glob_docs()
            if len(docs) != 1:
                parser.error(
                    f"{len(docs)} .docx files found, "
                    f"please specify input"
                )
            self.args.input, = docs
            print(f"Working on the only .docx here, {self.args.input}")

        if not self.args.stem:
            self.args.stem = self.args.input.stem

    def pre_work(self) -> Path:
        self.parse_args()
        print(f"Reading {self.args.input}")
        return self.args.input

    def work(self):
        self.randomize()

        num_pnodes = 0
        self.body = self.find(self.doc, "./w:body")
        pnodes = list(self.xpath(self.body, "./w:p"))
        meat_pnodes = []

        self.color_background()

        l2ps = defaultdict(list)
        for pnode in pnodes:
            text = "".join(tnode.text for tnode in self.pnode_tnodes(pnode))
            if self.args.contains:
                if not re.search(self.args.contains, text):
                    continue
            meat = re.sub(r"[^א-תa-zA-Z]", "", text)
            if meat:
                l2ps[meat].append(pnode)
                meat_pnodes.append(pnode)
                num_pnodes += 1

        print(f"Number of unique lines: {len(l2ps)} of {num_pnodes}")
        new_pnodes = [
            random.choice(pnodes)
            for pnodes in l2ps.values()
        ]
        self.rng.shuffle(new_pnodes)
        self.reorder(new_pnodes)
        self.write_as("shuffled")

        self.reorder([
            pnode
            for line, pnodes in sorted(l2ps.items())
            for pnode in pnodes
        ])
        self.write_as("sorted")

        self.reorder([
            pnode
            for line, pnodes in sorted(
                l2ps.items(),
                key=lambda item: "".join(reversed(item[0]))
            )
            for pnode in pnodes
        ])
        self.write_as("detros")

        if not self.args.model:
            return

        with open(self.args.model, "r", encoding="utf-8") as mfo:
            model_lines = []
            for line in mfo:
                line = line.strip()
                if line and not line.startswith("#"):
                    line = re.sub(r"[^a-z ]", "", line.lower())
                    model_lines.append(line)
        if (n_model := len(model_lines)) != (n_meat := len(meat_pnodes)):
            print(f"Cannot use model (n={n_model}) to sort text (n={n_meat})")
            return

        self.reorder([
            meat_pnodes[idx]
            for idx in np.argsort(model_lines)
        ])
        self.write_as("msort")

    def color_background(self):
        """Change paper color in the shuffled files"""
        if self.find(self.body, "./w:background") is None:
            self.body.append(self.make_w(
                "background",
                attrib={
                    "color": "FF2CC",
                    "themeColor": "accent4",
                    "themeTint": "33",
                },
            ))

    def randomize(self):
        """Read/Write random seed file"""
        self.rng = np.random.default_rng()
        if self.args.one_time_seed:
            return

        seed_path = self.args.input.with_suffix(".seed")
        try:
            with open(seed_path, "rb") as fobj:
                loaded = pickle.load(fobj)
                if not isinstance(loaded, np.random.Generator):
                    print(f"Incompatible {seed_path}, regenerating")
                    raise TypeError()
            print(f"Random state loaded from {seed_path}")

            self.rng = loaded
        except (FileNotFoundError, TypeError, pickle.UnpicklingError):
            print(f"Saving random state to {seed_path}")
            with open(seed_path, "wb") as fobj:
                pickle.dump(self.rng, fobj)

    def reorder(self, pnodes):
        """Replace paragraphs with new order"""
        for pnode in list(self.xpath(self.body, "./w:p")):
            self.body.remove(pnode)
        self.body.extend(pnodes)

    def write_as(self, suffix: str):
        """Write a version of the file"""
        path = self.args.input.with_stem(f"{self.args.stem}-{suffix}")
        print(f"Writing {path}")
        self.write(path)


if __name__ == "__main__":
    DocxShuffle().main()
