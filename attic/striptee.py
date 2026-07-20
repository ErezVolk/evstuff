#!/usr/bin/env python3
"""Act as tee (stripping ANSI codes)."""
import re
import sys
from pathlib import Path

_HELP = {"-?", "-h", "--help"}

# ECMA-48: 2-byte Fe escapes and CSI sequences (covers SGR color codes)
_ANSI = re.compile(rb"\x1B(?:[@-Z\\-_]|\x5B[0-9;?]*[ -/]*[@-~])")


def _usage(progname: str) -> None:
    print(
        f"Usage: {progname} [FILE...]\n"
        f"\n"
        f"Like tee(1), but strips ANSI control codes from log, and with multiple logs."
    )


def striptee(fns: list[str], logs: list) -> None:
    """Act as tee (stripping ANSI codes)."""
    if fns:
        with Path(fns[0]).open("wb") as log:
            striptee(fns[1:], [*logs, log])
    else:
        out = sys.stdout.buffer
        for line in iter(sys.stdin.buffer.readline, b""):
            out.write(line)
            out.flush()
            for log in logs:
                log.write(_ANSI.sub(b"", line))
                log.flush()


if __name__ == "__main__":
    args = sys.argv[1:]
    if _HELP.intersection(args):
        _usage(sys.argv[0])
    else:
        striptee(args, [])




