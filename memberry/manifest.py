"""File-hash manifests for incremental memory updates.

A manifest records the SHA-256 of every ingested source file (relative path
→ hash) so a later ``update`` can tell what changed without re-touching
Cognee unnecessarily. One JSON file per dataset, stored under the system root
(outside the repo), so it never pollutes the user's project.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import Settings


def manifest_path(settings: Settings, dataset: str) -> Path:
    """Return the on-disk manifest path for ``dataset``."""
    return settings.system_root / "manifests" / f"{dataset}.json"


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's raw bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, str]:
    """Load the ``{relpath: hash}`` map, or ``{}`` if missing/unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    files = data.get("files") if isinstance(data, dict) else None
    return files if isinstance(files, dict) else {}


def save_manifest(path: Path, repo: str, files: dict[str, str]) -> None:
    """Persist a manifest of ``files`` for ``repo`` to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"repo": repo, "files": files}
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def diff_manifests(
    prev: dict[str, str], curr: dict[str, str]
) -> tuple[list[str], list[str], list[str]]:
    """Compare two manifests, returning ``(added, modified, removed)`` paths."""
    added = sorted(k for k in curr if k not in prev)
    removed = sorted(k for k in prev if k not in curr)
    modified = sorted(k for k in curr if k in prev and prev[k] != curr[k])
    return added, modified, removed
