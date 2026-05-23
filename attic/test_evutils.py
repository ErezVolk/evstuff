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
    assert punp(parser, ["--string", "hello"]) == ["--string", "hello"]


def test_take_long_options(parser: ArgumentParser) -> None:
    parser.add_argument("-1", "-2", "--one", "--two")
    cli = punp(parser, ["-1", "zwei"])
    assert cli[1] == "zwei"
    assert cli[0] in ["--one", "--two"]


def test_unparse_store_true(parser: ArgumentParser) -> None:
    parser.add_argument("-y", action="store_true")
    assert punp(parser, []) == []
    assert punp(parser, ["-y"]) == ["-y"]


def test_path_arg(parser: ArgumentParser) -> None:
    parser.add_argument("-p", type=Path)
    assert punp(parser, ["-p", "this"]) == ["-p", str(Path("this").resolve())]


def test_int_arg(parser: ArgumentParser) -> None:
    parser.add_argument("-i", type=int)
    assert punp(parser, ["-i", "123"]) == ["-i", "123"]


def test_positional(parser: ArgumentParser) -> None:
    parser.add_argument("a")
    parser.add_argument("b")
    assert punp(parser, ["one", "two"]) == ["one", "two"]


def test_zero_or_one(parser: ArgumentParser) -> None:
    parser.add_argument("-x", nargs="?")
    assert punp(parser, ["-x", "X"]) == ["-x", "X"]
    assert punp(parser, ["-x"]) == ["-x"]


# TODO: "?", "*", default=, const=


def punp(parser: ArgumentParser, cli: list[str]) -> list[str]:
    return evutils.unparse(parser, parser.parse_args(cli))


# /// script
# dependencies = ["pytest"]
# ///
