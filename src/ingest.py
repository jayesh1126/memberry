"""Ingest a software repository into Cognee memory.

The flow is deliberately small:

1. Walk the repo, keeping text/code files and skipping noise
   (``.git``, ``node_modules``, binaries, oversized files).
2. Tag each file's content with a path header so the graph knows its
   provenance.
3. Hand the whole batch to ``cognee.remember`` once, which structures and
   indexes it into the hybrid graph + vector store.

Everything Cognee-specific is funnelled through :func:`ingest_repo` so the
rest of MEMBERRY stays library-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .config import Settings, apply_to_cognee


@dataclass
class IngestResult:
    """Summary of an ingest run, returned to the CLI/server for reporting."""

    repo: str
    dataset: str
    files_ingested: int
    files_skipped: int
    bytes_ingested: int


def _is_probably_binary(path: Path, sniff_bytes: int = 2048) -> bool:
    """Heuristically detect binary files by looking for NUL bytes."""
    try:
        with path.open("rb") as handle:
            chunk = handle.read(sniff_bytes)
    except OSError:
        return True
    return b"\x00" in chunk


def iter_source_files(repo: Path, settings: Settings) -> Iterator[Path]:
    """Yield ingestable source files under ``repo``.

    Skips excluded directories, non-source extensions, oversized files,
    and anything that sniffs as binary.
    """
    repo = repo.resolve()
    exclude = set(settings.exclude_dirs)
    include = set(settings.include_extensions)

    for path in repo.rglob("*"):
        if path.is_dir():
            continue
        # Skip if any path part is an excluded directory.
        if exclude.intersection(path.parts):
            continue
        if path.suffix.lower() not in include:
            continue
        try:
            if path.stat().st_size > settings.max_file_bytes:
                continue
        except OSError:
            continue
        if _is_probably_binary(path):
            continue
        yield path


def _read_text(path: Path) -> str | None:
    """Read a file as UTF-8 text, returning ``None`` if it cannot be decoded."""
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return None


def _as_document(repo: Path, path: Path, content: str) -> str:
    """Wrap file content with a header so provenance survives into the graph."""
    rel = path.resolve().relative_to(repo.resolve())
    return f"# FILE: {rel.as_posix()}\n\n{content}"


async def ingest_repo(repo_path: str, settings: Settings, dataset: str | None = None) -> IngestResult:
    """Ingest ``repo_path`` into a Cognee dataset and build the memory graph.

    Args:
        repo_path: Path to the repository root to remember.
        settings: Active :class:`~src.config.Settings`.
        dataset: Optional dataset/namespace; defaults to ``settings.default_dataset``.

    Returns:
        An :class:`IngestResult` describing what was stored.
    """
    import cognee

    apply_to_cognee(settings)

    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise FileNotFoundError(f"Repo path is not a directory: {repo}")

    dataset = dataset or settings.default_dataset

    documents: list[str] = []
    skipped = total_bytes = 0
    for path in iter_source_files(repo, settings):
        content = _read_text(path)
        if content is None or not content.strip():
            skipped += 1
            continue
        documents.append(_as_document(repo, path, content))
        total_bytes += len(content.encode("utf-8"))

    if documents:
        # One lifecycle call ingests, structures, and self-improves the whole
        # batch (Cognee 1.x `remember`). self_improvement is on by default.
        await cognee.remember(documents, dataset_name=dataset)

    return IngestResult(
        repo=str(repo),
        dataset=dataset,
        files_ingested=len(documents),
        files_skipped=skipped,
        bytes_ingested=total_bytes,
    )
