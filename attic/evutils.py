"""Common utilities."""
# ruff: noqa: SLF001, C901, PLW2901
import argparse
from pathlib import Path


def unparse(parser: argparse.ArgumentParser, args: argparse.Namespace) -> list[str]:
    """Create arguments that, when parsed with `parser`, create `args`."""
    optionals: list[str] = []
    positionals: list[str] = []

    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue

        which = optionals if (opts := action.option_strings) else positionals

        vals = []
        if isinstance(action, argparse._StoreTrueAction):
            if not getattr(args, action.dest):
                continue
        elif isinstance(action, argparse._StoreAction):
            value = getattr(args, action.dest)
            if value is None:
                if action.nargs != argparse.OPTIONAL:
                    continue
            else:
                for elem in (value if isinstance(value, list) else [value]):
                    if isinstance(elem, Path):
                        elem = elem.resolve()
                    vals.append(str(elem))

        if opts:
            which.append(
                next((opt for opt in opts if opt.startswith("--")), opts[0])
            )
        which.extend(vals)
    return [*optionals, *positionals]
