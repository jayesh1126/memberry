"""Memory lifecycle operations beyond ingest/recall: improve and forget.

These map MEMBERRY onto the back half of Cognee's memory lifecycle
(``remember`` → ``recall`` → ``improve`` → ``forget``). Keeping them here
leaves :mod:`src.ingest` focused on crawling and remembering a repo.
"""

from __future__ import annotations

from .config import Settings, apply_to_cognee


async def improve_memory(settings: Settings, dataset: str | None = None) -> str:
    """Run Cognee's post-ingestion enrichment (``improve``) on a dataset.

    Prunes stale nodes and adapts the graph so recall sharpens over time.
    Returns the dataset that was improved.
    """
    import cognee

    apply_to_cognee(settings)
    dataset = dataset or settings.default_dataset
    await cognee.improve(dataset=dataset)
    return dataset


async def forget_memory(
    settings: Settings, dataset: str | None = None, everything: bool = False
) -> str:
    """Delete memory via Cognee's ``forget``.

    Deletes a single dataset, or all of them when ``everything`` is True.
    Returns the dataset name forgotten, or ``"*"`` for everything.
    """
    import cognee

    apply_to_cognee(settings)
    if everything:
        await cognee.forget(everything=True)
        return "*"
    dataset = dataset or settings.default_dataset
    await cognee.forget(dataset=dataset)
    return dataset
