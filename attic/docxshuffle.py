#!/usr/bin/env python3
"""Shuffle paragraphs in a Word document."""
import argparse
import pickle
import random
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from docx_worker import DocxWorker
from lxml import etree


class DocxShuffle(DocxWorker):
    """Shuffle paragraphs in a Word document."""

    args: argparse.Namespace
    body: etree._Entity
    rng: np.random.Generator
    l2ps: dict[str, etree._Entity]
    meat_pnodes: list[etree._Entity]
    seed_path: Path

    def parse_args(self) -> None:
        """Parse command-line options."""
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
            help=(
                "a text file with at least the same number of lines "
                "as the input, will use the ordering of the file"
            ),
        )
        parser.add_argument(
            "-s",
            "--stem",
            type=Path,
            help="Common part of all output files",
        )
        parser.add_argument(
            "-S",
            "--one-time-seed",
            action="store_true",
            help="do NOT read the seed file, reshuffle every time",
        )
        parser.add_argument(
            "-c",
            "--contains",
            metavar="REGEX",
            help="only shuffle lines containing REGEX",
        )
        parser.add_argument(
            "-l",
            "--min-length",
            type=int,
            default=1,
            help="exclude lines shorter than this",
        )
        parser.add_argument(
            "-L",
            "--max-length",
            type=int,
            help="exclude lines longer than this",
        )
        parser.add_argument(
            "-C",
            "--keep-comments",
            action="store_true",
            help="do NOT strip baloons",
        )
        self.args = parser.parse_args()
        if self.args.input is None:
            docs = self.glob_docs()
            if len(docs) != 1:
                parser.error(
                    f"{len(docs)} .docx files found, please specify input",
                )
            (self.args.input,) = docs
            print(f"Working on the only .docx here, {self.args.input}")

        if not self.args.stem:
            self.args.stem = self.args.input.stem

    def pre_work(self) -> Path:
        """Return path of docx to read."""
        self.parse_args()
        print(f"Reading {self.args.input}")
        return self.args.input

    def work(self) -> None:
        """DO the actual work."""
        self.randomize()

        if not self.args.keep_comments:
            etree.strip_elements(
                self.doc,
                self.wtag("commentReference"),
                self.wtag("commentRangeStart"),
                self.wtag("commentRangeEnd"),
            )

        self.body = self.find(self.doc, "./w:body")
        self.parse_text()

        new_pnodes = [random.choice(pnodes) for pnodes in self.l2ps.values()]
        self.rng.shuffle(new_pnodes)
        self.reorder(new_pnodes)
        self.write_as("shuffled")

        self.reorder(
            [
                pnode
                for line, pnodes in sorted(self.l2ps.items())
                for pnode in pnodes
            ],
        )
        self.write_as("sorted")

        self.reorder(
            [
                pnode
                for line, pnodes in sorted(
                    self.l2ps.items(),
                    key=lambda item: "".join(reversed(item[0])),
                )
                for pnode in pnodes
            ],
        )
        self.write_as("detros")

        self.reorder(
            [
                pnodes[0]
                for line, pnodes in sorted(
                    self.l2ps.items(), key=lambda i: len(i[0]),
                )
            ],
        )
        self.write_as("growing")

        if not self.args.model:
            return

        with self.args.model.open("r", encoding="utf-8") as mfo:
            model_lines = []
            for unstripped in mfo:
                line = unstripped.strip()
                if line and not line.startswith("#"):
                    line = re.sub(r"\w", r"", line.lower())
                    model_lines.append(line)
        if (n_model := len(model_lines)) != (n_meat := len(self.meat_pnodes)):
            print(f"Cannot use model (n={n_model}) to sort text (n={n_meat})")
            return

        self.reorder([
            self.meat_pnodes[idx] for idx in np.argsort(model_lines)
        ])
        self.write_as("msort")

    def parse_text(self) -> None:
        """Read and normalize the contexts of the .docx file."""
        num_pnodes = 0
        pnodes = list(self.xpath(self.body, "./w:p"))
        self.meat_pnodes = []

        self.color_background()

        self.l2ps = defaultdict(list)
        for pnode in pnodes:
            text = "".join(tnode.text for tnode in self.pnode_tnodes(pnode))
            if len(text) < self.args.min_length:
                continue
            if self.args.max_length:
                if len(text) > self.args.max_length:
                    continue
            if self.args.contains:
                if not re.search(self.args.contains, text):
                    continue
            meat = re.sub(r"[^א-תa-zA-Z]", "", text)
            if not meat:
                continue
            self.l2ps[meat].append(pnode)
            self.meat_pnodes.append(pnode)
            num_pnodes += 1

        print(f"Number of unique lines: {len(self.l2ps)} of {num_pnodes}")

    def color_background(self) -> None:
        """Change paper color in the shuffled files."""
        if self.find(self.body, "./w:background") is None:
            node = self.make_w(
                "background",
                attrib={
                    "color": "FF2CC",
                    "themeColor": "accent4",
                    "themeTint": "33",
                },
            )
            self.body.append(node)

    def randomize(self) -> None:
        """Read/Write random seed file."""
        self.rng = np.random.default_rng()
        self.seed_path = self.args.input.with_suffix(".seed")

        if not self.args.one_time_seed:
            if self.load_rng():
                return

        self.save_rng()

    def load_rng(self) -> bool:
        """Try to load the saved RNG state."""
        try:
            with self.seed_path.open("rb") as fobj:
                loaded = pickle.load(fobj)  # noqa: S301
                if not isinstance(loaded, np.random.Generator):
                    print(f"Incompatible {self.seed_path}, regenerating")
                    raise TypeError
            print(f"Random state loaded from {self.seed_path}")

            self.rng = loaded
        except (FileNotFoundError, TypeError, pickle.UnpicklingError):
            return False
        else:
            return True

    def save_rng(self) -> None:
        """Save RNG state."""
        print(f"Saving random state to {self.seed_path}")
        with self.seed_path.open("wb") as fobj:
            pickle.dump(self.rng, fobj)

    def reorder(self, pnodes: list[etree._Entity]) -> None:
        """Replace paragraphs with new order."""
        for pnode in list(self.xpath(self.body, "./w:p")):
            self.body.remove(pnode)
        self.body.extend(pnodes)

    def write_as(self, suffix: str) -> None:
        """Write a version of the file."""
        path = self.args.input.with_stem(f"{self.args.stem}-{suffix}")
        print(f"Writing {path}")
        self.write(path)


if __name__ == "__main__":
    DocxShuffle().main()
