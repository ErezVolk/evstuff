#!/usr/bin/env -S uv run --script
"""Unpair bluetooth devices."""
import argparse
import json
import shutil
import subprocess
import sys
import typing as t

import beaupy  # ty: ignore[unresolved-import]


def main() -> None:
    """Unpair bluetooth devices."""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-s",
        "--substring",
        help="Detach devices containing SUBSTRING.",
        default="Magic",
    )
    group.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Select devices interactively",
    )
    args = parser.parse_args()

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
    if not args.interactive:
        substring = args.substring.lower()
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
    main()

# /// script
# dependencies = ["beaupy"]
# ///
