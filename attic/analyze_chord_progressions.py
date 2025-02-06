#!/usr/bin/env python3
"""Analyze chord progressions."""
import abc
import collections
import contextlib
import re
import typing as t
from pathlib import Path

JCPC = Path("Jazz-Chord-Progressions-Corpus")
DB_ROOT = JCPC / "SongDB"


class Feedable(abc.ABC):
    """Something which can take chords."""

    @abc.abstractmethod
    def start(self) -> None:
        """Start a new song."""

    @abc.abstractmethod
    def feed(self, root: str, quad: str) -> None:
        """Add another quad."""


class Ngrammifier(Feedable):
    """Counts chord N-grams."""

    window: list[tuple[int, str]]

    def __init__(self, n: int) -> None:
        self.n = n
        self.counts = collections.Counter()

    def start(self) -> None:
        """Reset the window."""
        self.window = []

    def feed(self, root: str, quad: str) -> None:
        """Add another quad."""
        steps = self.to_num(root)
        if self.window:
            steps = ((steps - self.window[-1][0]) + 12) % 12

        self.window.append((steps, quad))
        if len(self.window) >= self.n:
            self.window = self.window[-self.n:]
            self._count()

    def _count(self) -> None:
        """Count a full ngram."""
        parts = [f"C{self.window[0][1]}"]
        cumu = 0
        for steps, quad in self.window[1:]:
            cumu += steps
            parts.append(f"{num2let(cumu)}{quad}")
        self.counts["\t".join(parts)] += 1

    @classmethod
    def to_num(cls, root: str) -> int:
        """Convert things like A# to a number in base-12."""
        base = "CCDDEFFGGAAB".index(root[0])
        if len(root) == 1:
            return base
        if root[1] == "b":
            return base - 1
        return base + 1


class MultiGrammifier(Feedable):
    """A collection of `Ngrammifier`s."""

    def __init__(self, ns: t.Iterable[int]) -> None:
        self.fiers = {n: Ngrammifier(n) for n in ns}

    def items(self) -> t.Iterable[tuple[int, Ngrammifier]]:
        """Wrap `self.fields.items()`."""
        return self.fiers.items()

    def start(self) -> None:
        """Reset the window."""
        for fier in self.fiers.values():
            fier.start()

    def feed(self, root: str, quad: str) -> None:
        """Add another quad."""
        for fier in self.fiers.values():
            fier.feed(root, quad)


class AnalyzeChordProgressions:
    """Analyze chord progressions."""

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
        self.parse()
        self.report()

    def parse(self) -> None:
        """Read songs and stuff."""
        self.mgram = MultiGrammifier(range(2, 6))
        for song_path in DB_ROOT.rglob("*.txt"):
            with song_path.open(encoding="utf-8") as song_fo:
                self.mgram.start()
                prev_symb = None
                for nline, line in enumerate(song_fo, 1):
                    sline = line.rstrip()
                    if not sline.startswith(" "):
                        continue
                    for mobj in re.finditer(r"([A-G][b#]?)(\S*)", sline):
                        if (symb := mobj.group(0)) == prev_symb:
                            continue
                        (root, quality) = mobj.groups()
                        try:
                            quad = self.get_quad(quality)
                        except KeyError:
                            print(f"{song_path}:{nline} {root!r} {quality!r}?")
                            raise

                        self.mgram.feed(root, quad)
                        prev_symb = symb

    def report(self) -> None:
        """Print interesting findings."""
        for n, fier in self.mgram.items():
            print(f"Top {n}-grams:")
            for seq, count in fier.counts.most_common(12):
                print(f"\t{seq}\t{count}")

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
    return LETTERS[num % 12]


if __name__ == "__main__":
    AnalyzeChordProgressions().run()
