#!/usr/bin/env python3
"""Random musical keys for practice"""
import argparse
import random

NOTES = (
    ("A"),
    ("A♯", "B♭"),
    ("B"),
    ("C"),
    ("C♯", "D♭"),
    ("D"),
    ("D♯", "E♭"),
    ("E"),
    ("F"),
    ("F♯", "G♭"),
    ("G"),
    ("G♯", "A♭"),
)

KEY_FIX = {
    "maj": {"A♯": "B♭", "B♯": "E♭", "C♯": "D♭", "D♯": "E♭", "G♯": "A♭"},
    "min": {"A♯": "B♭", "D♯": "E♭", "A♭": "G♯", "D♭": "C♯", "G♭": "F♯"},
}

DRILLS = (
    "octaves", "fifths", "fourths", "chairs"
)

EASY_CHORDS = {
    "M": "maj",
    "m": "min",
    "7": "maj",
    "m7": "min",
    "M7": "maj",
    "dim7": "min",
}

CHORDS = EASY_CHORDS | {
    "6": "maj",
    "m7(-5)": "min",
}

DEFAULT_COUNTS = {
    "easy-chords": 3,
    "chords": 4,
}
DEFAULT_COUNT = len(NOTES)


def main():
    """Random musical keys for practice"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "what",
        choices=["notes", "scales", "drills", "easy-chords", "chords"],
        default="drills",
        nargs="?",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
    )
    parser.add_argument(
        "-c",
        "--chords",
        type=str,
        nargs="+"
    )
    args = parser.parse_args()

    if args.count is None:
        args.count = DEFAULT_COUNTS.get(args.what, DEFAULT_COUNT)

    if "chords" in args.what:
        sep = "\n"
        if args.chords is not None:
            choices = args.chords
        elif args.what == "easy-chords":
            choices = EASY_CHORDS
        else:
            choices = CHORDS
        notes = random.choice(NOTES)
        start = random.choice(notes)
        things = [f"* start from {'/'.join(notes)}"] + [
            f" - {KEY_FIX[CHORDS[chord]].get(start, start)}{chord}, etc."
            for chord in choose(choices, args.count)
        ]
    else:
        sep = " "

        things = [
            random.choice(names)
            for names in choose(NOTES, args.count)
        ]

        if args.what == "chords":
            things = things + things
            chords = choose(CHORDS, len(things))
            things = [
                KEY_FIX[CHORDS[chord]].get(thing, thing) + chord
                for thing, chord in zip(things, chords)
            ]

        if args.what in ["scales", "drills"]:
            scales = choose(KEY_FIX, len(things))
            things = [
                KEY_FIX[scale].get(thing, thing) + "-" + scale
                for thing, scale in zip(things, scales)
            ]

            if args.what == "drills":
                drills = choose(DRILLS, len(things))
                things = [
                    f"{thing} in {drill}"
                    for thing, drill in zip(things, drills)
                ]
                sep = "\n"

    print(sep.join(things))


def choose(options, n) -> list[str]:
    if n <= len(options):
        return random.sample(list(options), max(n, 1))
    rounds = (n + len(options) - 1) // len(options)
    choices = list(options) * rounds
    random.shuffle(choices)
    return choices[:n]


if __name__ == "__main__":
    main()
