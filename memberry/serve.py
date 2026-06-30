"""FastAPI HTTP server exposing MEMBERRY recall (and ingest) over HTTP.

Designed so an AI coding agent can hit a single endpoint to fetch
persistent codebase context:

    GET  /health
    POST /recall   {"query": "...", "mode": "answer", "dataset": "..."}
    GET  /recall?query=...&mode=...
    POST /ingest   {"repo": "/path/to/repo", "dataset": "..."}

Run via ``python memberry.py serve`` (see :func:`run`).
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .ingest import ingest_repo
from .lifecycle import forget_memory, improve_memory
from .recall import DEFAULT_MODE, recall
from .update import update_memory


class RecallRequest(BaseModel):
    """Body for ``POST /recall``."""

    query: str = Field(..., description="Natural-language question about the repo")
    mode: str = Field(DEFAULT_MODE, description="answer|graph|rag|chunks|insights|summaries")
    dataset: Optional[str] = Field(None, description="Dataset/namespace to query")


class RecallResponse(BaseModel):
    """Response for recall endpoints."""

    query: str
    mode: str
    dataset: str
    answer: str


class IngestRequest(BaseModel):
    """Body for ``POST /ingest``."""

    repo: str = Field(..., description="Path to the repository root to remember")
    dataset: Optional[str] = Field(None, description="Dataset/namespace to write")


class IngestResponse(BaseModel):
    """Response for the ingest endpoint."""

    repo: str
    dataset: str
    files_ingested: int
    files_skipped: int
    bytes_ingested: int


class DatasetRequest(BaseModel):
    """Body for lifecycle endpoints that act on a whole dataset."""

    dataset: Optional[str] = Field(None, description="Dataset/namespace name")
    everything: bool = Field(False, description="forget only: wipe ALL datasets")


class UpdateRequest(BaseModel):
    """Body for ``POST /update``."""

    repo: str = Field(..., description="Path to the repository root to sync")
    dataset: Optional[str] = Field(None, description="Dataset/namespace name")
    full: bool = Field(False, description="Force a full rebuild")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application bound to the given settings."""
    settings = settings or load_settings()
    app = FastAPI(
        title="MEMBERRY",
        version="0.1.0",
        summary="Codebase memory for AI coding agents, powered by Cognee.",
    )

    @app.get("/health")
    async def health() -> dict:
        """Liveness probe and a peek at the active dataset."""
        return {"status": "ok", "dataset": settings.default_dataset}

    @app.post("/recall", response_model=RecallResponse)
    async def recall_post(req: RecallRequest) -> RecallResponse:
        """Recall codebase context for a question (JSON body)."""
        try:
            result = await recall(req.query, settings, mode=req.mode, dataset=req.dataset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RecallResponse(**_result_dict(result))

    @app.get("/recall", response_model=RecallResponse)
    async def recall_get(
        query: str, mode: str = DEFAULT_MODE, dataset: Optional[str] = None
    ) -> RecallResponse:
        """Recall codebase context via query string (handy for quick curls)."""
        try:
            result = await recall(query, settings, mode=mode, dataset=dataset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RecallResponse(**_result_dict(result))

    @app.post("/ingest", response_model=IngestResponse)
    async def ingest_post(req: IngestRequest) -> IngestResponse:
        """Ingest a repository into memory (JSON body)."""
        try:
            result = await ingest_repo(req.repo, settings, dataset=req.dataset)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return IngestResponse(**result.__dict__)

    @app.post("/update")
    async def update_post(req: UpdateRequest) -> dict:
        """Sync a dataset's memory with the repo's current state."""
        try:
            result = await update_memory(
                req.repo, settings, dataset=req.dataset, full=req.full
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "dataset": result.dataset,
            "added": result.added,
            "modified": result.modified,
            "removed": result.removed,
            "rebuilt": result.rebuilt,
            "changed": result.changed,
        }

    @app.post("/improve")
    async def improve_post(req: DatasetRequest) -> dict:
        """Enrich/sharpen memory for a dataset (lifecycle ``improve``)."""
        dataset = await improve_memory(settings, dataset=req.dataset)
        return {"status": "improved", "dataset": dataset}

    @app.post("/forget")
    async def forget_post(req: DatasetRequest) -> dict:
        """Delete a dataset, or everything (lifecycle ``forget``)."""
        target = await forget_memory(
            settings, dataset=req.dataset, everything=req.everything
        )
        return {"status": "forgotten", "dataset": target}

    return app


def _result_dict(result) -> dict:
    """Pick the response fields from a RecallResult (drops the raw payload)."""
    return {
        "query": result.query,
        "mode": result.mode,
        "dataset": result.dataset,
        "answer": result.answer,
    }


def run(host: str | None = None, port: int | None = None) -> None:
    """Start the Uvicorn server. Called by the ``serve`` CLI subcommand."""
    import uvicorn

    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host=host or settings.host, port=port or settings.port)
