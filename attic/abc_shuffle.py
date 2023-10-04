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
    "maj": {"A♯": "B♭", "B♯": "E♭", "C♯": "D♭", "G♯": "A♭"},
    "min": {"A♯": "B♭", "D♯": "E♭", "A♭": "G♯", "D♭": "C♯", "G♭": "F♯"},
}


def main():
    """Random musical keys for practice"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "what",
        choices=["notes", "scales"],
        default="notes",
        nargs="?",
    )
    args = parser.parse_args()

    things = [
        random.choice(names)
        for names in random.sample(NOTES, len(NOTES))
    ]
    if args.what == "scales":
        scales = list(KEY_FIX) * (len(things) // len(KEY_FIX))
        random.shuffle(scales)
        things = [
            KEY_FIX[scale].get(thing, thing) + scale
            for thing, scale in zip(things, scales)
        ]

    print(" ".join(things))


if __name__ == "__main__":
    main()
