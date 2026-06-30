"""Tests for MEMBERRY's library-agnostic plumbing.

These tests deliberately avoid hitting Cognee or any LLM. They cover the
pure logic we own: settings loading, file crawling/filtering, mode->search
type mapping, and result stringification. That keeps CI fast and runnable
without API keys.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the project root importable when running ``pytest`` from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memberry.config import load_settings  # noqa: E402
from memberry.ingest import iter_source_files  # noqa: E402
from memberry.recall import _MODE_TO_SEARCH_TYPE, _stringify  # noqa: E402


def test_load_settings_has_sane_defaults(monkeypatch):
    monkeypatch.delenv("MEMBERRY_PORT", raising=False)
    monkeypatch.delenv("MEMBERRY_DATASET", raising=False)
    settings = load_settings()
    assert settings.port == 8765
    assert settings.default_dataset == "memberry"
    assert settings.max_file_bytes > 0
    assert ".py" in settings.include_extensions


def test_iter_source_files_filters_noise(tmp_path: Path):
    (tmp_path / "keep.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# notes\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\x00\x00binary")
    nm = tmp_path / "node_modules" / "dep"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = {}\n", encoding="utf-8")

    settings = load_settings()
    found = {p.name for p in iter_source_files(tmp_path, settings)}

    assert "keep.py" in found
    assert "notes.md" in found
    assert "image.png" not in found          # wrong extension + binary
    assert "index.js" not in found           # inside node_modules


def test_iter_source_files_skips_oversized(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEMBERRY_MAX_FILE_KB", "1")
    big = tmp_path / "big.py"
    big.write_text("x = 0\n" * 5000, encoding="utf-8")  # > 1 KB
    small = tmp_path / "small.py"
    small.write_text("y = 1\n", encoding="utf-8")

    settings = load_settings()
    found = {p.name for p in iter_source_files(tmp_path, settings)}
    assert "small.py" in found
    assert "big.py" not in found


def test_every_mode_maps_to_a_search_type_member():
    # We can't always import cognee in CI, but every mode must reference a
    # plausible SearchType member name (upper snake case).
    for member in _MODE_TO_SEARCH_TYPE.values():
        assert member.isupper()
        assert member.replace("_", "").isalpha()


def test_modes_resolve_against_real_cognee_search_type():
    # When cognee IS installed, every mapped member must actually exist on
    # SearchType. This catches version drift (e.g. a removed `INSIGHTS`).
    cognee_search = pytest.importorskip("cognee.api.v1.search")
    search_type = cognee_search.SearchType
    valid = {m.name for m in search_type}
    missing = set(_MODE_TO_SEARCH_TYPE.values()) - valid
    assert not missing, f"recall modes map to non-existent SearchType: {missing}"


@pytest.mark.parametrize(
    "results,expected_fragment",
    [
        (["hello", "world"], "hello"),
        ([{"text": "from dict"}], "from dict"),
        ([{"content": "c-field"}], "c-field"),
        ([123, "tail"], "123"),
        ([], ""),
    ],
)
def test_stringify_handles_mixed_results(results, expected_fragment):
    out = _stringify(results)
    assert expected_fragment in out
