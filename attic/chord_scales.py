#!/usr/bin/env python3
"""Print which scales contain a given chord."""
import re

CHORD_TYPES = {
    "M7": [4, 7, 11],
    "ø7": [3, 6, 9],
    "7": [4, 7, 10],
    "m7": [3, 7, 10],
    "6": [4, 7, 9],
}

ACCIDENTALS = {
    "b": -1,
    "♭": -1,
    "#": 1,
    "♯": 1,
}

_NOTE_RE = (
    r"(?P<letter>[A-G])"
    r"(?P<accidental>[" + r"".join(ACCIDENTALS) + r"])?"
)

NOTE_RE = re.compile(_NOTE_RE)

CHORD_RE = re.compile(
    _NOTE_RE + r"(?P<type>" + r"|".join(CHORD_TYPES) + r")",
)

LETTER_TO_NUM = {
    letter: index
    for index, letter in enumerate("C D EF G A B")
    if letter != " "
}


def fix(note: int) -> int:
    """Normalize a note number."""
    while note < 0:
        note += 12
    return note % 12


def mobj_to_num(mobj: re.Match | None) -> int:
    """Convert match object of _NOTE_RE to a number."""
    assert mobj is not None
    num = LETTER_TO_NUM[mobj.group("letter")]
    if acc := mobj.group("accidental"):
        num = fix(num + ACCIDENTALS[acc])
    return num


NUM_TO_NOTE = {
    mobj_to_num(NOTE_RE.match(notes[0])): "/".join(notes)
    for notes in [
        ["C"],
        ["C♯", "D♭"],
        ["D"],
        ["D♯", "E♭"],
        ["E"],
        ["F"],
        ["F♯", "G♭"],
        ["G"],
        ["G♯", "A♭"],
        ["A"],
        ["A♯", "B♭"],
        ["B"],
    ]
}

KEY_TO_NUMS = {
    key: {fix(key + off) for off in LETTER_TO_NUM.values()}
    for key in range(12)
}


def run() -> None:
    """Print which scales contain a given chord."""
    while chords := input("Enter one or more chords: "):
        common_keys: set[int] | None = None
        for chord in chords.split():
            if not (mobj := CHORD_RE.fullmatch(chord.strip())):
                print(f"Cannot parse {chord!r}.")
                continue
            root = mobj_to_num(mobj)
            chord_nums = {root}
            for off in CHORD_TYPES[mobj.group("type")]:
                chord_nums.add(fix(root + off))
            chord_keys = {
                key
                for key, key_nums in KEY_TO_NUMS.items()
                if chord_nums.issubset(key_nums)
            }
            if common_keys is None:
                common_keys = chord_keys
            else:
                common_keys &= chord_keys
        if common_keys:
            print(
                "Matching key(s):",
                ", ".join(NUM_TO_NOTE[num] for num in common_keys),
            )
        else:
            print("No matching keys!")


if __name__ == "__main__":
    run()
