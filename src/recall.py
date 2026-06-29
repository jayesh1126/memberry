"""Recall codebase context from Cognee memory.

A thin, typed wrapper around ``cognee.recall`` that maps friendly mode
names to Cognee ``SearchType`` values and normalises results into plain
strings the CLI and HTTP server can return verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import Settings, apply_to_cognee

# Friendly mode -> Cognee 1.x SearchType member name.
# Resolved lazily so MEMBERRY does not hard-depend on the enum layout.
# `auto` is special: it omits query_type so Cognee's auto_route picks the
# best strategy (semantic similarity vs deep graph traversal) per query.
_MODE_TO_SEARCH_TYPE = {
    "answer": "GRAPH_COMPLETION",    # natural-language answer grounded in the graph
    "graph": "GRAPH_COMPLETION",
    "rag": "RAG_COMPLETION",         # answer grounded in raw chunks
    "chunks": "CHUNKS",              # raw matching text chunks
    "triplets": "TRIPLET_COMPLETION",  # entity/relationship reasoning
    "summaries": "SUMMARIES",        # node summaries
    "code": "CODING_RULES",          # code-oriented rules/conventions
    "lucky": "FEELING_LUCKY",        # let Cognee decide everything
}

DEFAULT_MODE = "auto"


@dataclass
class RecallResult:
    """A recall response: the human-readable answer plus raw payload."""

    query: str
    mode: str
    dataset: str
    answer: str
    raw: list[Any] = field(default_factory=list)


def _resolve_search_type(mode: str):
    """Translate a friendly ``mode`` into a Cognee ``SearchType`` value."""
    from cognee.api.v1.search import SearchType  # local import keeps deps lazy

    member = _MODE_TO_SEARCH_TYPE.get(mode.lower())
    if member is None:
        valid = ", ".join(sorted(_MODE_TO_SEARCH_TYPE))
        raise ValueError(f"Unknown recall mode '{mode}'. Choose one of: {valid}")
    return getattr(SearchType, member)


_TEXT_FIELDS = ("answer", "text", "content", "result", "context", "completion")


def _stringify(results: list[Any]) -> str:
    """Flatten Cognee's heterogeneous result list into readable text.

    Handles plain strings, dicts, and Cognee 1.x pydantic response entries
    (which expose ``model_dump``), preferring obvious text-bearing fields.
    """
    parts: list[str] = []
    for item in results:
        if isinstance(item, str):
            parts.append(item)
            continue
        data = item.model_dump() if hasattr(item, "model_dump") else item
        if isinstance(data, dict):
            text = next((data[k] for k in _TEXT_FIELDS if data.get(k)), None)
            parts.append(str(text) if text is not None else str(data))
        else:
            parts.append(str(data))
    return "\n\n".join(p for p in parts if p).strip()


async def recall(
    query: str,
    settings: Settings,
    mode: str = DEFAULT_MODE,
    dataset: str | None = None,
) -> RecallResult:
    """Query codebase memory and return a normalised :class:`RecallResult`.

    Args:
        query: Natural-language question about the ingested repo.
        settings: Active :class:`~src.config.Settings`.
        mode: ``auto`` (let Cognee route) or one of ``answer``, ``graph``,
            ``rag``, ``chunks``, ``triplets``, ``summaries``, ``code``,
            ``lucky``.
        dataset: Optional dataset/namespace; defaults to the configured one.
    """
    import cognee

    apply_to_cognee(settings)

    dataset = dataset or settings.default_dataset

    # `auto` omits query_type so Cognee's auto_route chooses the strategy.
    kwargs: dict[str, Any] = {"datasets": [dataset]}
    if mode.lower() != "auto":
        kwargs["query_type"] = _resolve_search_type(mode)

    try:
        results = await cognee.recall(query, **kwargs)
    except Exception as exc:  # noqa: BLE001
        # An unknown/empty dataset (e.g. never ingested or just forgotten)
        # should read as "no memory", not crash with a traceback.
        if type(exc).__name__ == "DatasetNotFoundError":
            return RecallResult(
                query=query,
                mode=mode,
                dataset=dataset,
                answer=f"(no memory found for dataset '{dataset}' - run `ingest` first)",
                raw=[],
            )
        raise

    results = list(results or [])

    return RecallResult(
        query=query,
        mode=mode,
        dataset=dataset,
        answer=_stringify(results) or "(no relevant memory found)",
        raw=results,
    )
