#!/usr/bin/env -S uv run --script
"""Unpair bluetooth devices."""
import argparse
import json
import shutil
import subprocess
import sys
import typing as t

import beaupy  # ty: ignore[unresolved-import]

BLUETOOTH_PAGE = "x-apple.systempreferences:com.apple.preferences.Bluetooth"


class Demagic:
    """Unpair bluetooth devices."""

    blueutil: str

    def main(self) -> None:
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
        if blueutil:
            self.blueutil = blueutil
        else:
            self.fail("blueutil not found; install it with `brew install blueutil`")

        proc = self.run_blueutil(
            ["--paired", "--format", "json"],
            check=True,
            capture_output=True,
        )
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
            print("No devices to unpair.")
            return

        names = [f'"{dev["name"]}"' for dev in todo]
        addrs = [dev["address"] for dev in todo]
        input(f"Press Enter to unpair {' '.join(names)}...")
        for name, addr in zip(names, addrs, strict=True):
            print(f"Unpairing {name} ({addr})")
            proc = self.run_blueutil(["--unpair", addr], check=False)
            if proc.returncode == 0:
                print(" -> OK.")

        subprocess.run(["/usr/bin/open", BLUETOOTH_PAGE], check=False)

    def run_blueutil(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess:
        """Call blueutil."""
        return subprocess.run(
            [self.blueutil, *args],
            check=check,
            capture_output=capture_output,
        )

    def fail(self, message: str, code: int = -1) -> t.Never:
        """Print a message and exit."""
        print(message)
        sys.exit(code)


if __name__ == "__main__":
    Demagic().main()

# /// script
# dependencies = ["beaupy"]
# ///
