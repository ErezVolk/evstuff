#!/usr/bin/env -S uv run --script
"""Unpair bluetooth devices."""
import json
import shutil
import subprocess
import sys
import typing as t

import beaupy  # ty: ignore[unresolved-import]
import typer  # ty: ignore[unresolved-import]


def main(
    substring: t.Annotated[
        str,
        typer.Option("-s", "--substring", help="Detach devices containing SUBSTRING."),
    ] = "Magic",
    *,
    interactive: t.Annotated[
        bool,
        typer.Option(
            "-i",
            "--interactive",
            help="Select devices interactively (ignores SUBSTRING).",
        ),
    ] = False,
) -> None:
    """Unpair bluetooth devices."""
    blueutil = shutil.which("blueutil")
    if not blueutil:
        fail("blueutil not found; install it with `brew install blueutil`")

    def run(
        args: list[str],
        *,
        check: bool = False,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [blueutil, *args],
            check=check,
            capture_output=capture_output,
        )

    proc = run(["--paired", "--format", "json"], check=True, capture_output=True)
    devices = json.loads(proc.stdout)
    if not interactive:
        substring = substring.lower()
        todo = [dev for dev in devices if substring in dev.get("name", "").lower()]
    else:
        indices = beaupy.select_multiple(
            [dev["name"] for dev in devices],
            return_indices=True,
        )
        todo = [devices[idx] for idx in indices]

    if not todo:
        print("No matching devices found.")
        return

    names = [f'"{dev["name"]}"' for dev in todo]
    addrs = [dev["address"] for dev in todo]
    input(f"Press Enter to unpair {' '.join(names)}...")
    for name, addr in zip(names, addrs, strict=True):
        print(f"Unpairing {name} ({addr})")
        proc = run(["--unpair", addr], check=False)
        if proc.returncode == 0:
            print(" -> OK.")

    subprocess.run(
        ["/usr/bin/open", "x-apple.systempreferences:com.apple.preferences.Bluetooth"],
        check=False,
    )


def fail(message: str, code: int = -1) -> t.Never:
    """Print a message and exit."""
    print(message)
    sys.exit(code)


if __name__ == "__main__":
    typer.run(main)

# /// script
# dependencies = ["typer", "beaupy"]
# ///
