"""Tests for the CLI surface and lifecycle wiring.

Parser tests run offline (no Cognee). The graceful-recall test runs only
when Cognee is installed, but stubs out the network so it stays fast and free.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import memberry  # noqa: E402


def test_parser_dispatches_each_subcommand():
    parser = memberry.build_parser()

    assert parser.parse_args(["ingest", "--repo", "x"]).func is memberry._cmd_ingest
    assert parser.parse_args(["recall", "q"]).func is memberry._cmd_recall
    assert parser.parse_args(["improve"]).func is memberry._cmd_improve
    assert parser.parse_args(["forget"]).func is memberry._cmd_forget
    assert parser.parse_args(["serve"]).func is memberry._cmd_serve


def test_verbose_flag_works_after_subcommand():
    parser = memberry.build_parser()
    assert parser.parse_args(["recall", "q", "--verbose"]).verbose is True
    assert parser.parse_args(["recall", "q"]).verbose is False


def test_forget_all_and_recall_options_parse():
    parser = memberry.build_parser()
    assert parser.parse_args(["forget", "--all"]).all is True
    args = parser.parse_args(["recall", "q", "--mode", "triplets", "--json"])
    assert args.mode == "triplets"
    assert args.json is True


def test_lifecycle_functions_are_coroutines():
    from src import lifecycle

    assert asyncio.iscoroutinefunction(lifecycle.improve_memory)
    assert asyncio.iscoroutinefunction(lifecycle.forget_memory)


def test_recall_handles_missing_dataset_gracefully(monkeypatch):
    pytest.importorskip("cognee")
    import cognee

    from src import recall as recall_mod
    from src.config import load_settings

    class DatasetNotFoundError(Exception):
        """Mimics Cognee's error name; recall() matches on the class name."""

    async def boom(*args, **kwargs):
        raise DatasetNotFoundError("No datasets found.")

    monkeypatch.setattr(cognee, "recall", boom)

    result = asyncio.run(
        recall_mod.recall("anything", load_settings(), dataset="ghost")
    )
    assert "no memory found" in result.answer.lower()
    assert result.raw == []
