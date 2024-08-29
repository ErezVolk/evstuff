#!/usr/bin/env python3
"""Figure out whom is whom."""
import argparse
from pathlib import Path

import pandas as pd  # type: ignore[import-not-found]


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
        default="whoms.xlsx",
    )
    parser.add_argument(
        "-N",
        "--shortest-nth",
        type=int,
        default=2,
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=4,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args()

    albums = pd.read_excel(args.input)
    albums["heard"] = albums.When.notna()
    print(f"Heard {k_of_n(albums.heard)} albums")
    albums["Whom"] = albums.Whom.fillna("N/A")
    albums["Whoms"] = albums.Whom.str.replace(
        r"\s*[,&]\s*", "|", regex=True,
    ).str.split("|")

    whalbums = albums.explode("Whoms")
    whoms = whalbums.Whoms.value_counts().to_frame("total")
    whoms["heard"] = whalbums[whalbums.heard].Whoms.value_counts()
    whoms["heard"] = whoms.heard.fillna(0).astype(int)
    print(f"Heard {k_of_n(whoms.heard)} players")
    whoms["cov"] = whoms.heard / whoms.total
    print(f"Writing {len(whoms)} whoms to {args.output}")
    whoms.to_excel(args.output)
    if args.verbose:
        print(whoms.iloc[:10])
        print()

    unheard = albums.loc[albums.When.isna()]
    shorts = unheard.sort_values("dt").iloc[:len(unheard) // args.shortest_nth]
    offer = shorts.sample(n=args.count).sort_values("n")
    print(f"Suggestions ({len(offer)} of {len(shorts)} of {len(unheard)}):")
    for _, row in offer.iterrows():
        print(
            f'- [{row.n}] "{row.What}" ({row.t}) by {one_of(row.Who)} '
            f'(with {one_of(row.Whom)}, {row["dt"]})',
        )
    stars = whoms.query("heard == 0 and total > 1")
    if len(stars) > 0:
        stars = stars[stars.total == stars.total.max()]
        print(f" - Maybe something with {stars.sample(1).index[0]}?")


def k_of_n(heard: pd.Series) -> str:
    """Format "K of N (X%)"."""
    flags = heard > 0
    return f"{flags.sum()} of {len(flags)} ({flags.mean() * 100:.0f}%)"


def one_of(names: str) -> str:
    """For a list of names, return the first one."""
    for sep in ",&":
        if (off := names.find(sep)) > 0:
            return names[:off].strip() + " et al."
    return names


if __name__ == "__main__":
    main()
