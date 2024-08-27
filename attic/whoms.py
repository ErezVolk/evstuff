#!/usr/bin/env python3
"""Figure out whom is whom."""
import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    """Figure out whom is whom."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path.home() / "Dropbox" / "Private" / "albums.ods",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).with_suffix(".xlsx"),
    )
    args = parser.parse_args()

    albums = pd.read_excel(args.input)

    whoms = albums.Whom.value_counts().to_frame("total")
    whoms["heard"] = albums[albums.When.notna()].Whom.value_counts()
    whoms["heard"] = whoms.heard.fillna(0).astype(int)
    whoms["cov"] = whoms.heard / whoms.total
    print(f"Writing {len(whoms)} whoms to {args.output}")
    whoms.to_excel(args.output)

    unheard = albums[albums.When.isna()]
    shorts = unheard.sort_values("dt").iloc[:len(unheard) // 3]
    offer = shorts.sample(n=3).sort_values("n")
    print(f"Some suggestions ({len(offer)} of {len(shorts)}):")
    for _, row in offer.iterrows():
        print(f'- [{row.n}] "{row.What}" by {row.Who} ({row["dt"]})')


if __name__ == "__main__":
    main()
