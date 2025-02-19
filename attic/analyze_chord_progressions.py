#!/usr/bin/env python3
"""Analyze chord progressions."""
# pyright: reportMissingImports=false
import abc
import argparse
import collections
import contextlib
import random
import re
import typing as t
from pathlib import Path

import pandas as pd

JCPC = Path("Jazz-Chord-Progressions-Corpus")

Fields: t.TypeAlias = dict[str, str]


class Feedable(abc.ABC):
    """Something which can take chords."""

    @abc.abstractmethod
    def start(self, fields: Fields) -> None:
        """Start a new song."""

    @abc.abstractmethod
    def feed(self, symb: str, root: int, quad: str) -> None:
        """Add another quad."""


class Chord(t.NamedTuple):
    """A chord in a song."""

    symb: str
    root: int
    steps: int
    quad: str


class Ngrammifier(Feedable):
    """Counts chord N-grams."""

    path: Path
    window: list[Chord]
    fields: Fields
    offset: int

    def __init__(self, n: int) -> None:
        self.n = n
        self.counts = collections.Counter()
        self.firsts: dict[str, str] = {}
        self.records: list[Fields] = []

    def start(self, fields: Fields) -> None:
        """Reset the window."""
        self.window = []
        self.fields = fields
        self.offset = 0

    def feed(self, symb: str, root: int, quad: str) -> None:
        """Add another quad."""
        if self.window:
            steps = (root + 12 - self.window[-1].root) % 12
        else:
            steps = root

        self.window.append(Chord(symb, root, steps, quad))
        if len(self.window) >= self.n:
            self.window = self.window[-self.n:]
            self._count()

    def _count(self) -> None:
        """Count a full ngram."""
        roots = ["C"]
        parts = [f"C{self.window[0].quad}"]
        cumu = 0
        for chord in self.window[1:]:
            cumu += chord.steps
            roots.append(root := num2let(cumu))
            parts.append(f"{root}{chord.quad}")
        seq = "\t".join(parts)
        self.counts[seq] += 1
        symbs = [chord.symb for chord in self.window]
        name = self.fields.get("name", "???")
        key = self.fields.get("key", "?")
        self.firsts.setdefault(seq, f"[in {key}] {' '.join(symbs)} ({name})")

        self.offset += 1
        record = self.fields | {
            "offset": self.offset,
            "roots": " ".join(roots),
            "rels": " ".join(parts),
            "abss": " ".join(symbs),
        } | {
            f"roo_{n}": part
            for n, part in enumerate(roots, 1)
        } | {
            f"abs_{n}": symb
            for n, symb in enumerate(symbs, 1)
        } | {
            f"rel_{n}": part
            for n, part in enumerate(parts, 1)
        }
        self.records.append(record)

    def to_frame(self) -> pd.DataFrame:
        """Dump the whole thing."""
        return pd.DataFrame.from_records(self.records)


class MultiGrammifier(Feedable):
    """A collection of `Ngrammifier`s."""

    def __init__(self, ns: t.Iterable[int]) -> None:
        self.fiers = {n: Ngrammifier(n) for n in ns}

    def items(self) -> t.Iterable[tuple[int, Ngrammifier]]:
        """Wrap `self.fields.items()`."""
        return self.fiers.items()

    def start(self, fields: Fields) -> None:
        """Reset the window."""
        for fier in self.fiers.values():
            fier.start(fields)

    def feed(self, symb: str, root: int, quad: str) -> None:
        """Add another quad."""
        for fier in self.fiers.values():
            fier.feed(symb, root, quad)


class AnalyzeChordProgressions:
    """Analyze chord progressions."""

    args: argparse.Namespace
    mgram: MultiGrammifier

    @classmethod
    def sanity(cls) -> None:
        """Perform some sanity checks."""
        if not JCPC.is_dir():
            raise RuntimeError(
                "git clone https://github.com/carey-bunks/"
                "Jazz-Chord-Progressions-Corpus.git",
            )
        for src, dst in cls._DIFFS.items():
            if dst not in cls._SAMES:
                print(f"WARNING: {src!r} -> {dst!r} -> ?")

    def run(self) -> None:
        """Analyze chord progressions."""
        self.sanity()
        self.parse_args()
        self.parse()
        self.report()

    def parse(self) -> None:
        """Read songs and stuff."""
        self.mgram = MultiGrammifier(range(1, 6))
        paths = list(self.args.root.rglob("*.txt"))
        random.shuffle(paths)
        for path in paths:
            self.parse_song(path)

    def parse_args(self) -> None:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-r", "--root", type=Path, default=JCPC / "SongDB")
        parser.add_argument("--top-n", type=int, default=16)
        self.args = parser.parse_args()

    def parse_song(self, path: Path) -> None:
        """Parse one song."""
        with path.open(encoding="utf-8") as song_fo:
            fields: Fields = {"name": path.stem}
            self.mgram.start(fields)
            prev_symb = None
            for nline, line in enumerate(song_fo, 1):
                if not line.startswith(" "):
                    if mobj := re.fullmatch(r"(\S+) = (\S.*)\n?", line):
                        field, value = mobj.groups()
                        if field == "DBKeySig":
                            fields["key"] = value
                    continue
                for mobj in re.finditer(r"([A-G][b#]?)(\S*)", line):
                    if (symb := mobj.group(0)) == prev_symb:
                        continue

                    (root_str, quality) = mobj.groups()
                    try:
                        quad = self.get_quad(quality)
                    except KeyError:
                        print(f"{path}:{nline} {root_str!r} {quality!r}?")
                        raise

                    root = let2num(root_str)
                    with contextlib.suppress(IndexError, ValueError, KeyError):
                        if prev_symb is None:
                            fields["start"] = num2let(
                                root - let2num(fields["key"]),
                            )
                    self.mgram.feed(symb, root, quad)
                    prev_symb = symb

    def report(self) -> None:
        """Print interesting findings."""
        for n, fier in self.mgram.items():
            path = f"chord_{n}_grams.csv"
            frame = fier.to_frame()
            print(f"Writing {path} {frame.shape}")
            frame.to_csv(path, index=False)
            counts = fier.counts
            total = counts.total()
            mul = collections.Counter({
                gram: count
                for gram, count in counts.items()
                if count > 1
            })
            print(
                f"Top {n}-grams"
                f" (of {len(counts):,} / {total:,})"
                f" (non-unique {len(mul):,} / {mul.total():,})"
                f":",
            )
            for seq, count in counts.most_common(self.args.top_n):
                sample = fier.firsts[seq]
                percent = (count * 100) / total
                print(f"\t{seq}\t{count} ({percent:.01f}%)\te.g., {sample}")
            print("\n")

    _SAMES = frozenset([
        "",
        "+",
        "2",
        "4",
        "5",
        "6",
        "67",
        "6b5",
        "7",
        "7+",
        "7add6",
        "7alt",
        "7b5",
        "7b6",
        "7sus4",
        "M6",
        "M7",
        "M7+",
        "M7b5",
        "Mb5",
        "m",
        "m+",
        "m6",
        "m7",
        "m7+",
        "m7add4",
        "m7b5",
        "mM7",
        "mM7b6",
        "madd4",
        "mb5",
        "mb6",
        "no3",
        "o",
        "o7",
        "o7M7",
        "oM7",
        "sus2",
        "sus24",
        "sus4",
    ])
    _DIFFS: t.Mapping[str, str] = {
        "+7": "7+",
        "+add#9": "+",
        "+add9": "+",
        "11": "7",
        "13": "7",
        "13#11": "7",
        "13#9": "7",
        "13b5": "7b5",
        "13b9": "7",
        "13b9#11": "7",
        "13sus": "7sus4",
        "13sus4": "7sus4",
        "6#11": "6",
        "69": "6",
        "7#11": "7",
        "7#5": "7+",
        "7#5#9": "7+",
        "7#5b9": "7+",
        "7#5b9#11": "7+",
        "7#9": "7",
        "7#9#11": "7",
        "7#9b13": "7",
        "7add13": "7",
        "7alt": "7alt",
        "7b13": "7",
        "7b5#9": "7b5",
        "7b5b9": "7b5",
        "7b9": "7",
        "7b9#11": "7",
        "7b9b13": "7",
        "7b9b5": "7b5",
        "7b9sus4": "7sus4",
        "7sus": "7sus4",
        "7sus4b9": "7sus4",
        "7sus4b9b13": "7sus4",
        "7susb9": "7sus4",
        "9": "7",
        "9#11": "7",
        "9#5": "7+",
        "9+": "7+",
        "9b13": "7",
        "9b5": "7b5",
        "9sus": "7sus4",
        "9sus4": "7sus4",
        "M": "",
        "M#5add9": "+",
        "M13": "M7",
        "M13#11": "M7",
        "M69": "M6",
        "M69#11": "M6",
        "M7#11": "M7",
        "M7#5": "M7+",
        "M7#9#11": "M7",
        "M7#9b5": "M7b5",
        "M7add13": "M7",
        "M9": "M7",
        "M9#11": "M7",
        "M9#5": "M7+",
        "add9": "",
        "add9no3": "no3",
        "addb9": "",
        "dim": "o",
        "dim7": "o7",
        "h7": "m7b5",
        "m#5": "m+",
        "m11": "m7",
        "m11b5": "m7b5",
        "m13": "m7",
        "m69": "m6",
        "m7#5": "m7+",
        "m7add11": "m7",
        "m7b9": "m7",
        "m9": "m7",
        "m9b5": "m7b5",
        "mM9": "mM7",
        "mMaj7": "mM7",
        "madd9": "m",
        "maj13": "M7",
        "maj7": "M7",
        "maj7#5": "M7+",
        "maj9": "M7",
        "maj9#11": "M7",
        "mi": "m",
        "sus": "sus4",
        "susb9": "sus4",
    }
    QUADS = {quad: quad for quad in _SAMES} | _DIFFS

    @classmethod
    def get_quad(cls, quality: str) -> str:
        """Get just the stuff for the chord line."""
        with contextlib.suppress(ValueError):
            quality = quality[:quality.index("/")]
        if (quad := cls.QUADS.get(quality)) is not None:
            return quad
        raise KeyError(quality)


LETTERS = [
    "C",
    "Db",
    "D",
    "Eb",
    "E",
    "F",
    "Gb",
    "G",
    "Ab",
    "A",
    "Bb",
    "B",
]


def num2let(num: int) -> str:
    """Convert, e.g., 3 to 'Eb'."""
    while num < 0:
        num += 12
    return LETTERS[num % 12]


def let2num(letter: str) -> int:
    """Convert things like A# to a number in base-12."""
    base = "CCDDEFFGGAAB".index(letter[0])
    if len(letter) == 1:
        return base
    if letter[1] == "b":
        return base - 1
    return base + 1


if __name__ == "__main__":
    AnalyzeChordProgressions().run()
