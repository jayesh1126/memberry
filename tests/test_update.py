"""Tests for incremental update logic.

Manifest diffing and the no-change fast path run offline (no Cognee). The
change-applying path runs only when Cognee is installed, with the network
calls stubbed so it stays fast and free.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import manifest  # noqa: E402
from src.config import load_settings  # noqa: E402


def _isolated(tmp_path: Path):
    """Return (settings, repo_dir) with storage kept OUTSIDE the repo.

    Storage must live outside the repo, else the manifest JSON would be
    re-scanned as a source file. Settings is frozen, so use ``replace``.
    """
    store = tmp_path / "store"
    repo = tmp_path / "repo"
    repo.mkdir()
    settings = replace(load_settings(), system_root=store, data_root=store)
    return settings, repo


def test_diff_manifests_classifies_changes():
    prev = {"a.py": "1", "b.py": "2", "c.py": "3"}
    curr = {"a.py": "1", "b.py": "CHANGED", "d.py": "4"}
    added, modified, removed = manifest.diff_manifests(prev, curr)
    assert added == ["d.py"]
    assert modified == ["b.py"]
    assert removed == ["c.py"]


def test_manifest_roundtrip(tmp_path: Path):
    path = tmp_path / "ds.json"
    files = {"src/x.py": "abc", "README.md": "def"}
    manifest.save_manifest(path, "/repo", files)
    assert manifest.load_manifest(path) == files
    assert manifest.load_manifest(tmp_path / "missing.json") == {}


def test_file_sha256_changes_with_content(tmp_path: Path):
    f = tmp_path / "f.txt"
    f.write_text("hello", encoding="utf-8")
    first = manifest.file_sha256(f)
    f.write_text("hello world", encoding="utf-8")
    assert manifest.file_sha256(f) != first


def test_update_no_change_skips_cognee(tmp_path: Path):
    # A matching manifest means update_memory should return "no change"
    # without importing Cognee — so this runs even without Cognee installed.
    from src import update

    settings, repo = _isolated(tmp_path)
    (repo / "mod.py").write_text("x = 1\n", encoding="utf-8")

    hashes, _ = update._scan(repo, settings)
    manifest.save_manifest(manifest.manifest_path(settings, "ds"), str(repo), hashes)

    result = asyncio.run(update.update_memory(str(repo), settings, dataset="ds"))
    assert result.changed is False
    assert result.rebuilt is False


def test_update_detects_modification(tmp_path: Path, monkeypatch):
    pytest.importorskip("cognee")
    import cognee

    from src import update

    settings, repo = _isolated(tmp_path)
    f = repo / "mod.py"
    f.write_text("x = 1\n", encoding="utf-8")
    hashes, _ = update._scan(repo, settings)
    manifest.save_manifest(manifest.manifest_path(settings, "ds"), str(repo), hashes)

    # Change the file, then stub the Cognee calls so no network/LLM is hit.
    f.write_text("x = 2\n", encoding="utf-8")

    async def fake_remember(*a, **k):
        return None

    async def fake_forget(*a, **k):
        return "ds"

    monkeypatch.setattr(cognee, "remember", fake_remember)
    monkeypatch.setattr(update, "forget_memory", fake_forget)

    result = asyncio.run(update.update_memory(str(repo), settings, dataset="ds"))
    assert result.modified == ["mod.py"]
    assert result.rebuilt is True
