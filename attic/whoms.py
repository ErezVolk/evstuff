#!/usr/bin/env python3
"""Figure out whom is whom."""
import argparse
from pathlib import Path
import tempfile
import subprocess

import pandas as pd  # type: ignore[import-not-found]


def main() -> None:
    """Figure out whom is whom."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--inputs",
        type=Path,
        nargs="+",
        default=[
            Path.home() / ".whoms.fods",
            Path.home() / ".whoms.ods",
            Path.home() / "Dropbox" / "Private" / "albums.ods",
        ],
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
        "-q",
        "--query",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "-w",
        "--write",
        action="store_true",
    )
    args = parser.parse_args()

    errors: list[str] = []
    for path in args.inputs:
        if path.is_file():
            albums = do_read(path)
            break
        if path.is_symlink():
            errors.append(f"Broken link: {path}...")
        elif path.exists(follow_symlinks=False):
            errors.append(f"Not a file: {path}...")
        else:
            errors.append(f"No {path}...")
    else:
        for error in errors:
            print(error)
        parser.error("Please specify --inputs")

    albums["heard"] = albums.When.notna()
    albums["Whom"] = albums.Whom.fillna("N/A")
    albums["Whoms"] = albums.Whom.str.replace(
        r"\s*[,&]\s*", "|", regex=True,
    ).str.split("|")

    whalbums = albums.explode("Whoms")
    whoms = whalbums.Whoms.value_counts().to_frame("total")
    whoms["heard"] = whalbums[whalbums.heard].Whoms.value_counts()
    whoms["heard"] = whoms.heard.fillna(0).astype(int)

    hours = albums["dt"].apply(lambda dt: dt.hour + dt.minute / 60)
    albums["minutes"] = hours * 60
    albums["hours"] = hours
    heards = [
        f"{k_of_n(albums.heard)} albums",
        f"{k_of_n(whoms.heard)} players",
        f"{x_of_y(int(hours[albums.heard].sum()), int(hours.sum()))} hours",
    ]
    print("Heard", ", ".join(heards))

    whoms["cov"] = whoms.heard / whoms.total
    if args.write:
        whoms.to_excel(args.output)
    if args.verbose:
        print(whoms.iloc[:10])
        print()

    unheard = albums.loc[albums.When.isna()]
    if args.query:
        unheard = unheard.query(args.query)
    if len(unheard) == 0:
        print("Time to find more music.")
    else:
        if args.shortest_nth:
            n_shortest = max(len(unheard) // args.shortest_nth, 1)
            shorts = unheard.sort_values("dt").iloc[:n_shortest]
        else:
            shorts = unheard
        offer = shorts.sample(n=min(args.count, len(shorts))).sort_values("n")
        print(f"Suggestions ({len(offer)} / {len(shorts)} / {len(unheard)}):")
        for _, row in offer.iterrows():
            print(f"- {row_desc(row)}")

        oldest_added = unheard.sort_values("n").iloc[0]
        print(f"- (oldest added) {row_desc(oldest_added)}")
        earliest_t = unheard.t.min()
        oldest_released = unheard[
            (unheard.t == earliest_t) & (unheard.What != oldest_added.What)
        ]
        if (n_rows := len(oldest_released)) > 0:
            row = oldest_released.sample(1).iloc[0]
            comment = f"one of {n_rows} " if n_rows > 1 else ""
            print(f"- ({comment}oldest released) {row_desc(row)}")

        guys = whoms.query("heard == 0")
        if len(stars := guys.query("total > 1")) > 0:
            starness = stars.total.max()
            star = stars[stars.total == starness].sample(1).index[0]
            works_with = unheard[unheard.Whom.str.contains(star, regex=False)]
            if len(works_with) > 0:
                row = works_with.sample(1).iloc[0]
                print(f"- ({starness}-popular new guy) {row_desc(row)}")
        elif len(names := set(guys.index)) > 0:
            works_with = albums[
                albums.Whoms.apply(lambda ppl: len(set(ppl) & names) > 0)
            ]
            rows = works_with[works_with.dt == works_with.dt.min()]
            n_rows = len(rows)
            row = rows.sample(1).iloc[0]
            comment = f"one of {n_rows} " if n_rows > 1 else ""
            print(f"- ({comment}shortest new guy) {row_desc(row)}")

    relisten = albums[albums.How.astype("string").str.contains("relisten")]
    if len(relisten) > 0:
        row = relisten.sample(1).iloc[0]
        print(f"- (relisten) {row_desc(row)}")


def do_read(path: Path) -> pd.DataFrame:
    """Actuall read a file."""
    if path.suffix.lower() == ".fods":
        zath = path.with_suffix(".ods")
        if not zath.is_file() or zath.stat().st_mtime < path.stat().st_mtime:
            subprocess.run([
                "soffice", "--headless", "--convert-to", "ods", str(path),
            ], check=True)
        path = zath
    return pd.read_excel(path)


def row_desc(row: pd.Series) -> str:
    """Nicely format a "to listen" row."""
    who = one_of(row.Who)
    whom = one_of(row.Whom)
    what = f'[{row.n}] "{row.What}" ({row.t}) by {one_of(row.Who)}'
    if who == whom and not who.endswith(" et al."):
        return f'{what} ({row["dt"]})'
    return f'{what} (with {one_of(row.Whom)}, {row["dt"]})'


def k_of_n(heard: pd.Series) -> str:
    """Format "K of N (X%)"."""
    flags = heard > 0
    return x_of_y(flags.sum(), len(flags))


def x_of_y(x: int, y: int) -> str:
    """Format "X of Y (Z%)"."""
    return f"{x:,} of {y:,} ({(x * 100) // (y)}%)"


def one_of(names: str) -> str:
    """For a list of names, return the first one."""
    for sep in ",&":
        if (off := names.find(sep)) > 0:
            return names[:off].strip() + " et al."
    return names


if __name__ == "__main__":
    main()
