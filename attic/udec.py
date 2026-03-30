#!/usr/bin/env python3
"""Trivial wrapper for unidecode."""
import sys

import unidecode  # type: ignore[import-not-found]


def decode_it() -> None:
    """Read input, decode it, write output."""
    for line in sys.stdin:
        nice = unidecode.unidecode(line)
        sys.stdout.write(nice)


if __name__ == "__main__":
    decode_it()
