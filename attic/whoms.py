#!/usr/bin/env python3
"""Figure out whom is whom."""
import argparse
import hashlib
import subprocess
import tempfile
import typing as t
from pathlib import Path

import pandas as pd  # type: ignore[import-not-found]


class Paths(t.NamedTuple):
    """Paths in conversion."""

    zath: Path
    oath: Path
    dath: Path


class Whoms:
    """Recommend an album."""

    parser: argparse.ArgumentParser
    args: argparse.Namespace

    def parse_cli(self) -> None:
        """Parse command-line arguments."""
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
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-g",
            "--git-commit",
            action="store_true",
        )
        group.add_argument(
            "-G",
            "--git-push",
            action="store_true",
            help="Do --git-commit, followed by git push",
        )
        parser.add_argument(
            "-C",
            "--convert-and-exit",
            action="store_true",
        )
        parser.add_argument(
            "-S",
            "--shortest-new-guys",
            action="store_true",
        )
        self.args = parser.parse_args()
        self.parser = parser

    def fail(self, msg: str) -> t.Never:
        """Fail because of the user."""
        self.parser.error(msg)

    def main(self) -> None:
        """Figure out whom is whom."""
        self.parse_cli()

        errors: list[str] = []
        for path in self.args.inputs:
            if path.is_file():
                albums = self.do_read(path)
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
            self.fail("Please specify --inputs")

        if not self.args.convert_and_exit:
            self.choose(albums)

    def choose(self, albums: pd.DataFrame) -> None:
        """Choose albums, print reports."""
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
        hours_total = hours.sum()
        hours_heard = hours[albums.heard].sum()
        heards = [
            f"{k_of_n(albums.heard)} albums",
            f"{k_of_n(whoms.heard)} players",
            f"{x_of_y(int(hours_heard), int(hours_total))} hours",
            f"median {int(albums.minutes.median())} ("
            f"heard: {int(albums[albums.heard].minutes.median())}, "
            f"unheard: {int(albums[~albums.heard].minutes.median())}"
            f") minutes",
        ]
        print("Heard", ", ".join(heards))

        whoms["cov"] = whoms.heard / whoms.total
        if self.args.write:
            whoms.to_excel(self.args.output)
        if self.args.verbose:
            print(whoms.iloc[:10])
            print()

        unheard = albums.loc[albums.When.isna()]
        if self.args.query:
            try:
                albums = albums.query(self.args.query)
                unheard = unheard.query(self.args.query)
            except NameError as exc:
                print("Bad query:", exc)
                return

        self.choose_unheard(albums, unheard, whoms)
        self.choose_heard(albums)

    def choose_unheard(
        self,
        albums: pd.DataFrame,
        unheard: pd.DataFrame,
        whoms: pd.DataFrame,
    ) -> None:
        """Choose among the unheard albums."""
        if len(unheard) == 0:
            print("Time to find more music.")
            return

        if self.args.shortest_nth:
            n_shortest = max(len(unheard) // self.args.shortest_nth, 1)
            shorts = unheard.sort_values("dt").iloc[:n_shortest]
        else:
            shorts = unheard
        sample_size = min(self.args.count, len(shorts))
        offer = shorts.sample(n=sample_size).sort_values("n")
        print(f"Suggestions ({len(offer)} / {len(shorts)} / {len(unheard)}):")
        for _, row in offer.iterrows():
            print(f"- {row_desc(row)}")

        n_oldest_added = unheard.sort_values("n").head()
        oldest_added = n_oldest_added.sample(1).iloc[0]
        print(f"- (one of {len(n_oldest_added)} oldest added) "
              f"{row_desc(oldest_added)}")
        earliest_t = unheard.t.min()
        oldest_released = unheard[
            (unheard.t == earliest_t) & (unheard.What != oldest_added.What)
        ]
        if (n_rows := len(oldest_released)) > 0:
            row = oldest_released.sample(1).iloc[0]
            comment = f"one of {n_rows} " if n_rows > 1 else ""
            print(f"- ({comment}oldest released) {row_desc(row)}")

        new_guys = whoms.query("heard == 0")
        if len(stars := new_guys.query("total > 1")) > 0:
            starness = stars.total.max()
            star = stars[stars.total == starness].sample(1).index[0]
            works_with = unheard[unheard.Whom.str.contains(star, regex=False)]
            if len(works_with) > 0:
                row = works_with.sample(1).iloc[0]
                print(f"- ({starness}-popular new guy) {row_desc(row)}")
        elif len(names := set(new_guys.index)) > 0:
            rows = albums[
                albums.Whoms.apply(lambda ppl: len(set(ppl) & names) > 0)
            ]
            parts = ["new guy"]
            if self.args.shortest_new_guys:
                rows = rows[rows.dt == rows.dt.min()]
                parts.insert(0, "shortest ")
            n_rows = len(rows)
            if n_rows > 1:
                parts.insert(0, f"one of {n_rows} ")
                parts.append("s")
            if n_rows > 0:
                row = rows.sample(1).iloc[0]
                print(f"- ({''.join(parts)}) {row_desc(row)}")

    def choose_heard(self, albums: pd.DataFrame) -> None:
        """Choose things to relisten to."""
        relisten = albums[albums.How.astype("string").str.contains("relisten")]
        if len(relisten) > 0:
            row = relisten.sample(1).iloc[0]
            print(f"- (relisten) {row_desc(row)}")

    def do_read(self, path: Path) -> pd.DataFrame:
        """Actuall read a file."""
        if path.suffix.lower() == ".fods":
            path = self.deflatten(path)
        return pd.read_excel(path)

    def deflatten(self, path: Path) -> Path:
        """Convert flat ODS to ODS."""
        while path.is_symlink():
            path = path.parent / path.readlink()
        path = path.absolute()
        digest = file_digest(path)

        math = path.with_name(f".auto-{path.stem}.fods")
        hath = path.with_name(f".auto-{path.stem}.digest")
        changed = read_digest(hath) != digest
        csv = self.deflatten_ext(path, math, "csv", changed=changed)
        with csv.dath.open("w", encoding="utf-8") as dfo:
            dfo.write(path.name)
            dfo.write("\n\n")

            if csv.oath.is_file():
                dfo.flush()

                cmd = [
                    "diff",
                    "-L before",
                    "-L after",
                    "-s", "-U0",
                    str(csv.oath), str(csv.zath),
                ]
                self.run(cmd, stdout=dfo, check=False, encoding="utf-8")

        ods = self.deflatten_ext(path, math, "ods", changed=changed)
        if changed:
            with hath.open("w", encoding="utf-8") as fobj:
                fobj.write(digest)
            if self.args.git_commit or self.args.git_push:
                flag = "-F" if self.args.git_commit else "-t"
                cmd = ["git", "commit", path.name, flag, csv.dath.name]
                print(">", " ".join(cmd))
                proc = self.run(cmd, cwd=path.parent, check=False)
                if proc.returncode == 0 and self.args.git_push:
                    cmd = ["git", "push"]
                    print(">", " ".join(cmd))
                    self.run(cmd, cwd=path.parent)

        return ods.zath

    def deflatten_ext(
        self,
        path: Path,
        math: Path,
        ext: str,
        *,
        changed: bool,
    ) -> Paths:
        """Deflatten one file."""
        zath = math.with_suffix(f".{ext}")
        oath = math.with_suffix(f".prev.{ext}")
        dath = math.with_suffix(f".diff.{ext}")

        exists = zath.is_file()
        if changed or not exists:
            print(f"{path} -> {zath}")
            if exists:
                zath.copy(oath)
                with tempfile.TemporaryDirectory() as tdir:
                    cmd = [
                        "soffice",
                        "--headless", "--convert-to", ext,
                        str(path),
                    ]
                    self.run(cmd, cwd=tdir, stdout=subprocess.PIPE)

                    created = Path(tdir) / f"{path.stem}.{ext}"
                    created.move(zath)
        return Paths(oath=oath, zath=zath, dath=dath)

    def run(
        self,
        args: list[str],
        *,
        check: bool = True,
        encoding: str | None = None,
        stdout: t.IO | int | None = None,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess:
        """Run the command described by args.

        Wraps `subprocess.run()`.
        """
        return subprocess.run(
            args,
            stdout=stdout,
            check=check,
            encoding=encoding,
            cwd=cwd,
        )


def file_digest(path: Path) -> str:
    """Generate hash of a file."""
    with path.open("rb") as fobj:
        return hashlib.file_digest(fobj, "md5").hexdigest()


def read_digest(path: Path) -> str | None:
    """Read the (hash) file."""
    try:
        with path.open("r", encoding="utf8") as fobj:
            return fobj.read().strip()
    except FileNotFoundError:
        return None


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
    Whoms().main()
