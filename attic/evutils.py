"""Common utilities."""
# ruff: noqa: SLF001
import argparse
from pathlib import Path


def unparse(parser: argparse.ArgumentParser, args: argparse.Namespace) -> list[str]:
    """Create arguments that, when parsed with `parser`, create `args`."""
    reverse_optionals: list[str] = []
    positionals: list[str] = []

    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue

        which = reverse_optionals if (opts := action.option_strings) else positionals

        if isinstance(action, argparse._StoreAction):
            value = getattr(args, action.dest)
            if value is not None:
                if isinstance(value, Path):
                    value = value.resolve()
                which.append(str(value))
            elif action.nargs != argparse.OPTIONAL:
                continue
        elif isinstance(action, argparse._StoreTrueAction):
            if not getattr(args, action.dest):
                continue

        if opts:
            reverse_optionals.append(
                next((opt for opt in opts if opt.startswith("--")), opts[0])
            )
    return [*reversed(reverse_optionals), *positionals]
