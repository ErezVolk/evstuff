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


def main():
    """Random musical keys for practice"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "what",
        choices=["notes", "scales", "drills"],
        default="drills",
        nargs="?",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=len(NOTES),
    )
    args = parser.parse_args()

    sep = " "

    if args.count <= len(NOTES):
        notes = random.sample(NOTES, max(args.count, 1))
    else:
        notes = random.choices(NOTES, k=args.count)

    things = [
        random.choice(names)
        for names in notes
    ]

    if args.what in ["scales", "drills"]:
        scales = random.choices(list(KEY_FIX), k=len(things))
        things = [
            KEY_FIX[scale].get(thing, thing) + "-" + scale
            for thing, scale in zip(things, scales)
        ]

    if args.what == "drills":
        drills = random.choices(DRILLS, k=len(things))
        things = [
            f"{thing} in {drill}"
            for thing, drill in zip(things, drills)
        ]
        sep = "\n"

    print(sep.join(things))


if __name__ == "__main__":
    main()
