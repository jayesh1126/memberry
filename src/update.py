"""Incremental memory updates — keep a dataset in sync with a changing repo.

``update_memory`` diffs the repo against the last-saved manifest and only
touches Cognee when something changed:

- **new files only** → incrementally ``remember`` just those files (cheap).
- **modified or removed files** → rebuild the dataset (``forget`` + re-ingest)
  so recall always reflects the current code. Surgical per-file deletion is a
  future optimization; rebuilding guarantees correctness today.

``watch_repo`` polls the repo and runs ``update_memory`` whenever it changes —
turning MEMBERRY into living memory that never goes stale.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import manifest
from .config import Settings, apply_to_cognee
from .ingest import _as_document, _read_text, iter_source_files
from .lifecycle import forget_memory


@dataclass
class UpdateResult:
    """What an update changed, returned to the CLI/server for reporting."""

    dataset: str
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    rebuilt: bool = False

    @property
    def changed(self) -> bool:
        """True if any file was added, modified, or removed."""
        return bool(self.added or self.modified or self.removed)


def _scan(repo: Path, settings: Settings) -> tuple[dict[str, str], dict[str, str]]:
    """Return ``(relpath→hash, relpath→document)`` for current source files."""
    hashes: dict[str, str] = {}
    documents: dict[str, str] = {}
    for path in iter_source_files(repo, settings):
        content = _read_text(path)
        if content is None or not content.strip():
            continue
        rel = path.resolve().relative_to(repo).as_posix()
        hashes[rel] = manifest.file_sha256(path)
        documents[rel] = _as_document(repo, path, content)
    return hashes, documents


async def update_memory(
    repo_path: str,
    settings: Settings,
    dataset: str | None = None,
    full: bool = False,
) -> UpdateResult:
    """Sync ``dataset``'s memory with the current state of ``repo_path``.

    Returns an :class:`UpdateResult`; makes no Cognee calls when nothing
    changed (unless ``full`` forces a rebuild).
    """
    repo = Path(repo_path).expanduser().resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"Repo path is not a directory: {repo}")

    dataset = dataset or settings.default_dataset
    mpath = manifest.manifest_path(settings, dataset)
    prev = manifest.load_manifest(mpath)

    curr_hashes, curr_docs = _scan(repo, settings)
    added, modified, removed = manifest.diff_manifests(prev, curr_hashes)
    result = UpdateResult(dataset, added, modified, removed)

    if not result.changed and not full:
        return result

    import cognee

    apply_to_cognee(settings)

    if full or modified or removed:
        # Rebuild for correctness (recall must not surface stale content).
        result.rebuilt = True
        if prev:
            try:
                await forget_memory(settings, dataset=dataset)
            except Exception as exc:  # noqa: BLE001 - tolerate already-gone dataset
                if type(exc).__name__ != "DatasetNotFoundError":
                    raise
        documents = list(curr_docs.values())
    else:
        # Only new files were added — remember just those.
        documents = [curr_docs[rel] for rel in added]

    if documents:
        await cognee.remember(documents, dataset_name=dataset)

    manifest.save_manifest(mpath, str(repo), curr_hashes)
    return result


def watch_repo(
    repo_path: str,
    settings: Settings,
    dataset: str | None = None,
    interval: float = 3.0,
    full: bool = False,
    on_update: Callable[[UpdateResult], None] | None = None,
) -> None:
    """Poll ``repo_path`` and run :func:`update_memory` whenever it changes.

    Blocks until interrupted (Ctrl+C). ``on_update`` is called with the
    :class:`UpdateResult` after each applied change.
    """
    repo = Path(repo_path).expanduser().resolve()
    dataset = dataset or settings.default_dataset
    last = manifest.load_manifest(manifest.manifest_path(settings, dataset))

    while True:
        time.sleep(interval)
        curr, _ = _scan(repo, settings)
        if manifest.diff_manifests(last, curr) == ([], [], []):
            continue
        result = asyncio.run(update_memory(str(repo), settings, dataset=dataset, full=full))
        last = curr
        if on_update is not None:
            on_update(result)
