#!/usr/bin/env -S uvx pytest -v
# ruff: noqa: D100, D103
# ty: ignore[unresolved-import]
from argparse import ArgumentParser
from pathlib import Path

import pytest

from . import evutils


@pytest.fixture
def parser() -> ArgumentParser:
    return ArgumentParser()


def test_unparse_string_arg(parser: ArgumentParser) -> None:
    parser.add_argument("--string")
    assert_punp(parser, ["--string", "hello"])


def test_take_long_options(parser: ArgumentParser) -> None:
    parser.add_argument("-1", "-2", "--one", "--two")
    cli = punp(parser, ["-1", "zwei"])
    assert cli[1] == "zwei"
    assert cli[0] in ["--one", "--two"]


def test_unparse_store_true(parser: ArgumentParser) -> None:
    parser.add_argument("-y", action="store_true")
    assert_punp(parser, [])
    assert_punp(parser, ["-y"])


def test_path_arg(parser: ArgumentParser) -> None:
    parser.add_argument("-p", type=Path)
    assert punp(parser, ["-p", "this"]) == ["-p", str(Path("this").resolve())]


def test_int_arg(parser: ArgumentParser) -> None:
    parser.add_argument("-i", type=int)
    assert_punp(parser, ["-i", "123"])


def test_positional(parser: ArgumentParser) -> None:
    parser.add_argument("a")
    parser.add_argument("b")
    assert_punp(parser, ["one", "two"])


def test_zero_or_one(parser: ArgumentParser) -> None:
    parser.add_argument("-x", nargs="?")
    assert_punp(parser, ["-x", "X"])
    assert_punp(parser, ["-x"])


def test_zero_or_more(parser: ArgumentParser) -> None:
    parser.add_argument("-x", nargs="*")
    assert_punp(parser, ["-x"])
    assert_punp(parser, ["-x", "1"])
    assert_punp(parser, ["-x", "1", "2"])


def test_one_or_more(parser: ArgumentParser) -> None:
    parser.add_argument("-y", nargs="*")
    assert_punp(parser, ["-y", "1"])
    assert_punp(parser, ["-y", "1", "2"])


# TODO: "+", default=, const=


def punp(parser: ArgumentParser, cli: list[str]) -> list[str]:
    return evutils.unparse(parser, parser.parse_args(cli))


def assert_punp(parser: ArgumentParser, cli: list[str]):
    assert punp(parser, cli) == cli


# /// script
# dependencies = ["pytest"]
# ///
