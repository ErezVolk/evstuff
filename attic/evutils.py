"""Common utilities."""
# ruff: noqa: SLF001, C901, PLW2901, PLR0912
import argparse
import shlex
import sys
from pathlib import Path


def write_runner(
    path: Path,
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    prog: Path | str | None = None,
) -> None:
    """Write a script to rerun the caller."""
    if prog is None:
        prog = Path(sys.argv[0])
    if isinstance(prog, Path):
        prog = str(prog.resolve())

    cli = [prog, *unparse(parser, args)]
    lines = [
        "#!/bin/sh",
        "# GENERATED FILE, DO NOT EDIT",
        "",
        " ".join(shlex.quote(elem) for elem in cli),
    ]
    with path.open("wt") as fobj:
        fobj.write("\n".join(lines))
    path.chmod(0o755)


def unparse(parser: argparse.ArgumentParser, args: argparse.Namespace) -> list[str]:
    """Create arguments that, when parsed with `parser`, create `args`."""
    optionals: list[str] = []
    positionals: list[str] = []

    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue

        which = optionals if (opts := action.option_strings) else positionals

        ovalue = []
        if isinstance(action, argparse._StoreTrueAction):
            if not getattr(args, action.dest):
                continue
        elif isinstance(action, argparse._StoreAction):
            ivalue = getattr(args, action.dest)
            if ivalue is None:
                if action.nargs != argparse.OPTIONAL:
                    continue
            elif ivalue == action.default:
                continue
            elif action.nargs == argparse.OPTIONAL and ivalue == action.const:
                pass  # Include in output, but omit the value
            else:
                for item in (ivalue if isinstance(ivalue, list) else [ivalue]):
                    if isinstance(item, Path):
                        item = item.resolve()
                    ovalue.append(item)
        else:
            raise TypeError(f"Not supported: {action.__class__.__name__}")

        if opts:
            opt = next((opt for opt in opts if opt.startswith("--")), opts[0])
            which.append(opt)
        which.extend(map(str, ovalue))
    return [*optionals, *positionals]
