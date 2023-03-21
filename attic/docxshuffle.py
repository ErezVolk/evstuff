#!/usr/bin/env python3
import argparse
from collections import defaultdict
from pathlib import Path
import random
import re

from docx_worker import DocxWorker


class DocxShuffle(DocxWorker):
    def parse_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "input",
            type=Path,
            nargs="?",
        )
        parser.add_argument(
            "-s",
            "--stem",
            type=Path,
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

        inpath = self.args.input
        if not self.args.stem:
            self.args.stem = inpath.stem

    def pre_work(self) -> Path:
        self.parse_args()
        print(f"Reading {self.args.input}")
        return self.args.input

    def work(self):
        num_pnodes = 0
        body = self.find(self.doc, "./w:body")
        old_pnodes = list(self.xpath(body, "./w:p"))

        l2ps = defaultdict(list)
        for pnode in old_pnodes:
            text = "".join(tnode.text for tnode in self.pnode_tnodes(pnode))
            text = re.sub(r"[^א-תa-zA-Z]", "", text)
            if text:
                l2ps[text].append(pnode)
                num_pnodes += 1

        print(f"Number of unique lines: {len(l2ps)} of {num_pnodes}")
        for pnode in old_pnodes:
            body.remove(pnode)
        new_pnodes = [
            random.choice(pnodes)
            for pnodes in l2ps.values()
        ]
        random.shuffle(new_pnodes)
        body.extend(new_pnodes)
        self.write_as("shuffled")

        for pnode in new_pnodes:
            body.remove(pnode)
        new_pnodes = [
            pnode
            for line, pnodes in sorted(l2ps.items())
            for pnode in pnodes
        ]
        body.extend(new_pnodes)
        self.write_as("sorted")

        for pnode in new_pnodes:
            body.remove(pnode)
        new_pnodes = [
            pnode
            for line, pnodes in sorted(
                l2ps.items(),
                key=lambda item: "".join(reversed(item[0]))
            )
            for pnode in pnodes
        ]
        body.extend(new_pnodes)
        self.write_as("detros")

    def write_as(self, suffix: str):
        path = self.args.input.with_stem(f"{self.args.stem}-{suffix}")
        print(f"Writing {path}")
        self.write(path)


if __name__ == "__main__":
    DocxShuffle().main()
