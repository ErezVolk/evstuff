#!/usr/bin/env -S uv run --script
"""Figure out whom is whom."""

import argparse
import hashlib
import importlib
import shlex
import subprocess
import tempfile
import time
import typing as t
from pathlib import Path

import pandas as pd  # ty: ignore[unresolved-import]
import scipy.stats  # ty: ignore[unresolved-import]


class Paths(t.NamedTuple):
    """Paths in conversion."""

    curr: Path
    prev: Path
    diff: Path


class Stats(t.NamedTuple):
    """Stats of a collection of album lengths."""

    desc: str
    mean: float
    std: float
    nobs: int

    def __str__(self) -> str:
        return self.desc


class Whoms:
    """Recommend an album."""

    parser: argparse.ArgumentParser
    args: argparse.Namespace
    times: dict[str, float]
    ALPHA = 0.05

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
            "-o",
            "--output",
            type=Path,
            nargs="?",
            const="whoms.xlsx",
            help="Write XLSX output",
        )
        parser.add_argument(
            "-p",
            "--graph",
            type=Path,
            nargs="?",
            const="whoms.pdf",
            help="Create PDF with some statistics",
        )
        parser.add_argument(
            "-I",
            "--interact",
            action="store_true",
            help="Enter interactive mode"
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
        parser.add_argument(
            "-R",
            "--relisten-all",
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

        self.times = {}
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

        if self.args.verbose:
            self.report_times()

    def choose(self, albums: pd.DataFrame) -> None:
        """Choose albums, print reports."""
        albums["heard"] = albums.When.notna()
        albums["Whom"] = albums.Whom.fillna("").replace(
            r"^([?]+|N/A)$", "", regex=True
        )
        albums["Whoms"] = albums.Whom.str.replace(
            r"\s*[,&]\s*", "|", regex=True,
        ).str.split("|")

        whalbums = albums.explode("Whoms").query("Whoms != ''")
        whoms = whalbums.Whoms.value_counts().to_frame("total")
        whoms["heard"] = whalbums[whalbums.heard].Whoms.value_counts()
        whoms["heard"] = whoms.heard.fillna(0).astype(int)

        hours = albums["dt"].apply(lambda dt: dt.hour + dt.minute / 60)
        albums["minutes"] = hours * 60
        albums["hours"] = hours
        hours_total = hours.sum()
        hours_heard = hours[albums.heard].sum()
        heard_stats = self.describe(albums[albums.heard].minutes)
        unheard_stats = self.describe(albums[~albums.heard].minutes)
        sep = "≉" if self.different(heard_stats, unheard_stats) else "≈"
        heards = [
            f"{k_of_n(albums.heard)} albums",
            f"{k_of_n(whoms.heard)} players",
            f"{x_of_y(int(hours_heard), int(hours_total))} hours",
            f"{self.describe(albums.minutes)} ("
            f"heard: {heard_stats}"
            f" {sep} "
            f"unheard: {unheard_stats}"
            f")",
        ]
        print("Heard", ", ".join(heards))

        whoms["cov"] = whoms.heard / whoms.total
        if self.args.output:
            whoms.to_excel(self.args.output)
        if self.args.graph:
            self.write_pdf(self.args.graph, albums)
        if self.args.verbose:
            print(whoms.iloc[:5])
            print()

        unheard = albums.loc[albums.When.isna()]
        if self.args.query:
            try:
                albums = albums.query(self.args.query)
                unheard = unheard.query(self.args.query)
            except (NameError, KeyError) as exc:
                print("Bad query:", exc)
                return
            if albums.empty:
                print("This query leaves nothing, it's probably incorrect.")
                return
            if unheard.empty:
                print("Already heard everything in this query.")
                return

        if not unheard.empty:
            self.choose_unheard(albums, unheard, whoms)
        else:
            print("Time to find more music.")
        self.choose_heard(albums)

        if self.args.interact:
            which = albums.Which.str.title().replace(  # noqa: F841
                r"\s*\([^)]*\)", "", regex=True
            ).str.strip().replace(
                r"\s*,\s*", ",", regex=True
            ).str.split(
                ","
            ).explode().to_frame().join(
                albums[["n", "Who", "What"]]
            ).reset_index(drop=True).query(
                'Which.notna() and Which != ""'
            )

            ipy = importlib.import_module("IPython")  # Lazy import since why force it
            config = ipy.terminal.ipapp.load_default_config()
            config.InteractiveShellEmbed = config.TerminalInteractiveShell
            config.InteractiveShellEmbed.confirm_exit = False
            ipy.embed(header="Check out albums, whoms, unheard, which", config=config)

    @classmethod
    def describe(cls, minutes: pd.Series) -> Stats:
        """Format floating-point minutes as a MEAN±SD string."""
        return Stats(
            nobs=len(minutes),
            mean=(mean := minutes.mean()),
            std=(std := minutes.std()),
            desc=f"{cls.mmss(mean)}±{cls.ss(std)}",
        )

    @classmethod
    def mmss(cls, minutes: float) -> str:
        """Format floating-point minutes as mm:ss."""
        mm = int(minutes)
        ss = int((minutes - mm) * 60)
        if ss == 0:
            return f"{mm}m"
        return f"{mm}:{ss:02d}"

    @classmethod
    def ss(cls, minutes: float) -> str:
        """Format floating-point minutes as ss."""
        return f"{int(minutes * 60)}s"

    def choose_unheard(
        self,
        albums: pd.DataFrame,
        unheard: pd.DataFrame,
        whoms: pd.DataFrame,
    ) -> None:
        """Choose among the unheard albums."""
        self.show_wip(unheard)
        if self.args.shortest_nth:
            n_shortest = max(len(unheard) // self.args.shortest_nth, 1)
            shorts = unheard.sort_values("dt").iloc[:n_shortest]
        else:
            shorts = unheard
        sample_size = min(self.args.count, len(shorts))
        offer = shorts.sample(n=sample_size).sort_values("n")
        print(f"Suggestions ({len(offer)} / {len(shorts)} / {len(unheard)}):")
        self.print_rows(offer)

        n_oldest_added = unheard.sort_values("n").head()
        oldest_added = n_oldest_added.sample(1).iloc[0]
        print(f"- (one of {len(n_oldest_added)} oldest added) "
              f"{row_desc(oldest_added)}")
        the_rest = unheard.drop(oldest_added.name)

        if not the_rest.empty:
            n_oldest_released = the_rest.sort_values("t").head()
            oldest_released = n_oldest_released.sample(1).iloc[0]
            print(f"- (one of {len(n_oldest_released)} oldest released) "
                  f"{row_desc(oldest_released)}")
            the_rest = unheard.drop(oldest_released.name)

        if not the_rest.empty:
            n_longest = the_rest.sort_values("minutes").tail()
            longest = n_longest.sample(1).iloc[0]
            print(f"- (one of {len(n_longest)} longest) "
                  f"{row_desc(longest)}")

        new_guys = whoms.query("heard == 0")
        if len(stars := new_guys.query("total > 1")) > 0:
            starness = stars.total.max()
            star = stars[stars.total == starness].sample(1).index[0]
            works_with = unheard[self.substr_map(unheard.Whom, star)]
            self.print_one_of(works_with, f"{starness}-popular new guy")
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
                self.print_one_of(rows, "".join(parts))

    def show_wip(self, unheard: pd.DataFrame) -> pd.DataFrame:
        """Remind user of work in progress."""
        is_wip = self.substr_map(unheard.How, "WIP")
        n_wip = sum(is_wip)
        if n_wip > 0:
            print(f"Work In Progress ({n_wip}):")
            self.print_rows(unheard[is_wip])

        unheard = unheard[~is_wip]
        sus = unheard[unheard.How.notna()]
        n_sus = len(sus)
        if n_sus > 0:
            print(f"Unheard but described ({n_sus}):")
            self.print_rows(sus)
        return unheard

    def choose_heard(self, albums: pd.DataFrame) -> None:
        """Choose things to relisten to."""
        relisten = albums[self.substr_map(albums.How, "relisten")]
        if self.args.relisten_all or (n_relisten := len(relisten)) <= 1:
            relisten = albums[albums.When.notna()]
            inset = "relisten"
        else:
            inset = f"relisten out of {n_relisten}"
        self.print_one_of(relisten, inset)

    def report_times(self) -> None:
        """Print what took so long."""
        if not self.times:
            return
        print("\nDurations:")
        for cmd, duration in sorted(self.times.items(), key=lambda e: -e[1]):
            print(f" [{duration:.02f} Sec]\t{cmd}")

    def print_rows(self, rows: pd.DataFrame) -> None:
        """Print a list of albums."""
        for _, row in rows.iterrows():
            print(f"- {row_desc(row)}")

    def print_one_of(self, rows: pd.DataFrame | pd.Series, inset: str) -> None:
        """Print one random album with an extra text."""
        if rows.empty:
            return
        print(f"- ({inset}) {row_desc(rows.sample(1).iloc[0])}")

    @classmethod
    def substr_map(cls, series: pd.Series, substr: str) -> pd.Series:
        """Return Series[boolean] of values containing substring."""
        as_str = series.astype("string").str
        return as_str.contains(substr, regex=False, case=False).fillna(value=False)

    def do_read(self, path: Path) -> pd.DataFrame:
        """Actually read a file, deflattening if required."""
        return pd.read_excel(
            self.deflatten(path) if path.suffix.lower() == ".fods" else path
        )

    def write_pdf(self, path: Path, albums: pd.DataFrame) -> None:
        """Write some stats as a graph."""
        sns = importlib.import_module("seaborn")  # Lazy import since it's slow
        sns.set()
        fig = sns.displot(
            data=albums,
            x="minutes", hue="heard",
            kde=True,
        )
        print(f"Writing {path}")
        fig.savefig(path)

    def deflatten(self, flat: Path) -> Path:
        """Convert FODS to ODS (for reading) and CSV (for diff). Return the ODS."""
        while flat.is_symlink():
            flat = flat.parent / flat.readlink()
        flat = flat.absolute()
        digested = file_digest(flat)

        model = flat.with_name(f".auto-{flat.stem}.model")
        intestine = model.with_suffix(".digested")
        changed = self._is_changed(flat, intestine, digested)
        csv = self.deflatten_to(flat, model, "csv", changed=changed, diffable=True)
        with csv.diff.open("w", encoding="utf-8") as dfo:
            dfo.write(flat.name)
            dfo.write("\n\n")

            if csv.prev.is_file():
                dfo.flush()

                cmd = [
                    "diff",
                    "-L before",
                    "-L after",
                    "-s", "-U0",
                    str(csv.prev), str(csv.curr),
                ]
                self.run(cmd, redirect=dfo, check=False, encoding="utf-8")

        ods = self.deflatten_to(flat, model, "ods", changed=changed)
        if changed:
            intestine.write_text(digested, encoding="UTF-8")
            if self.args.git_commit or self.args.git_push:
                flag = "-F" if self.args.git_commit else "-t"
                args = ["commit", flat.name, flag, csv.diff.name]
                proc = self.git(args, cwd=flat.parent, check=False)
                if proc and proc.returncode == 0 and self.args.git_push:
                    self.git(["push"], cwd=flat.parent)

        return ods.curr

    def _is_changed(self, path: Path, intestine: Path, digested: str) -> bool:
        args = ["diff", "--quiet", path.name]
        proc = self.git(
            args, cwd=path.parent, check=False, echo=False, redirect=subprocess.DEVNULL
        )
        if proc:
            if proc.returncode == 0:
                return False
            if proc.returncode == 1:
                return True
        return read_digest(intestine) != digested

    def deflatten_to(
        self,
        path: Path,
        model: Path,
        extension: str,
        *,
        changed: bool,
        diffable: bool = False,
    ) -> Paths:
        """Deflatten one file to one format."""
        curr = model.with_suffix(f".{extension}")
        prev = model.with_suffix(f".prev.{extension}")
        diff = model.with_suffix(f".diff.{extension}")

        if changed or not curr.is_file():
            with tempfile.TemporaryDirectory() as tdir:
                tpath = Path(tdir)
                if changed and diffable:
                    self._checkout_and_convert(path, prev, tpath)
                self._convert(path, curr, tpath)
        return Paths(prev=prev, curr=curr, diff=diff)

    def _checkout_and_convert(self, flat: Path, dest: Path, where: Path) -> None:
        args = ["show", f"HEAD:./{flat.name}"]
        prev_flat = where / flat.name
        with prev_flat.open("wb") as pfo:
            proc = self.git(args, cwd=flat.parent, check=False, redirect=pfo)
            if proc is None or proc.returncode != 0:
                return
        self._convert(prev_flat, dest, where, f"{flat.name}@HEAD")

    def _convert(
        self, flat: Path, dest: Path, where: Path, disp: str | None = None
    ) -> None:
        print(f"{disp or flat.name} -> {dest.name}")
        cmd = [
            "soffice",
            "--headless", "--convert-to", dest.suffix.removeprefix("."),
            str(flat),
        ]
        self.run(cmd, cwd=where, redirect=subprocess.DEVNULL)

        created = where / f"{flat.stem}{dest.suffix}"
        created.move(dest)

    @classmethod
    def different(cls, stat1: Stats, stat2: Stats) -> bool:
        """Check whether two stats are significantly different."""
        ttest = scipy.stats.ttest_ind_from_stats(
            stat1.mean, stat1.std, stat1.nobs,
            stat2.mean, stat2.std, stat2.nobs,
        )
        return ttest.pvalue <= cls.ALPHA

    def git(
        self,
        args: list[str],
        cwd: Path,
        *,
        check: bool = True,
        redirect: t.IO | int | None = None,
        echo: bool = True,
    ) -> subprocess.CompletedProcess | None:
        """Run a Git command."""
        cmd = ["git", *args]
        if echo:
            print(">", " ".join(cmd))
        try:
            return self.run(cmd, cwd=cwd, check=check, redirect=redirect)
        except FileNotFoundError:
            return None

    def run(
        self,
        args: list[str],
        *,
        check: bool = True,
        encoding: str | None = None,
        redirect: t.IO | int | None = None,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess:
        """Run the command described by args.

        Wraps `subprocess.run()`.
        """
        start_time = time.monotonic()
        proc = subprocess.run(
            args,
            stdout=redirect,
            stderr=redirect,
            check=check,
            encoding=encoding,
            cwd=cwd,
        )
        duration = time.monotonic() - start_time
        self.times[" ".join(map(shlex.quote, args))] = duration
        return proc


def file_digest(path: Path) -> str:
    """Generate hash of a file."""
    with path.open("rb") as fobj:
        return hashlib.file_digest(fobj, "md5").hexdigest()


def read_digest(path: Path) -> str | None:
    """Read the (hash) file."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def row_desc(row: pd.Series) -> str:
    """Nicely format a "to listen" row."""
    who = one_of(row.Who)
    whom = one_of(row.Whom)
    what = f'[{row.n}] "{row.What}" ({row.t}) by {one_of(row.Who)}'
    if not whom or (who == whom and not who.endswith(" et al.")):
        return f'{what} ({row["dt"]})'
    return f'{what} (with {whom}, {row["dt"]})'


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

# /// script
# requires-python = ">=3.14"
# dependencies = ["pandas", "scipy", "seaborn", "odfpy", "ipython"]
# ///
