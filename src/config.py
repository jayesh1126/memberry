"""Configuration for MEMBERRY.

All settings come from environment variables (optionally loaded from a
local ``.env`` file). Nothing is hardcoded and there is no global mutable
state beyond the cached ``Settings`` dataclass that callers pass around.

The single source of truth for talking to Cognee lives here: call
:func:`apply_to_cognee` once at startup to push our settings into the
Cognee library before any ingest/recall happens.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

# python-dotenv warns on any non KEY=VALUE line in .env; those warnings are
# cosmetic (the bad line is skipped), so keep them out of clean CLI output.
logging.getLogger("dotenv").setLevel(logging.CRITICAL)

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass


# Default set of file extensions worth remembering from a code repo.
DEFAULT_INCLUDE_EXTENSIONS = (
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java",
    ".kt", ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp", ".cc",
    ".swift", ".scala", ".sh", ".bash", ".sql", ".md", ".rst", ".txt",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
)

# Directories that never carry useful codebase memory.
DEFAULT_EXCLUDE_DIRS = (
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", "out", "target", ".idea",
    ".vscode", ".mypy_cache", ".pytest_cache", ".ruff_cache", "coverage",
    ".cache", "vendor", "site-packages",
)


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings, assembled from the environment."""

    llm_api_key: str
    llm_provider: str
    llm_model: str
    llm_endpoint: str
    embedding_provider: str
    embedding_model: str
    embedding_endpoint: str
    embedding_dimensions: str
    huggingface_tokenizer: str
    data_root: Path
    system_root: Path
    default_dataset: str
    host: str
    port: int
    max_file_bytes: int
    include_extensions: tuple[str, ...] = field(default=DEFAULT_INCLUDE_EXTENSIONS)
    exclude_dirs: tuple[str, ...] = field(default=DEFAULT_EXCLUDE_DIRS)


def _env(name: str, default: str = "") -> str:
    """Return an environment variable, trimmed, falling back to ``default``."""
    return os.environ.get(name, default).strip()


def load_settings() -> Settings:
    """Build a :class:`Settings` instance from environment variables.

    Recognised variables (all optional except the LLM key for live runs):

    - ``LLM_API_KEY``      API key for the LLM provider Cognee uses.
    - ``LLM_PROVIDER``     e.g. ``openai`` (default), ``anthropic``, ``ollama``.
    - ``LLM_MODEL``        chat/completion model name.
    - ``EMBEDDING_MODEL``  embedding model name.
    - ``MEMBERRY_DATA_DIR``    where Cognee stores raw data.
    - ``MEMBERRY_SYSTEM_DIR``  where Cognee stores its databases.
    - ``MEMBERRY_DATASET``     default dataset/namespace name.
    - ``MEMBERRY_HOST`` / ``MEMBERRY_PORT``  HTTP server bind address.
    - ``MEMBERRY_MAX_FILE_KB`` skip files larger than this (default 256 KB).
    """
    home = Path(_env("MEMBERRY_HOME", str(Path.home() / ".memberry")))
    data_root = Path(_env("MEMBERRY_DATA_DIR", str(home / "data")))
    system_root = Path(_env("MEMBERRY_SYSTEM_DIR", str(home / "system")))
    max_kb = int(_env("MEMBERRY_MAX_FILE_KB", "256") or "256")

    return Settings(
        # Leave provider/model defaults empty so Cognee's own sensible
        # defaults (openai/gpt-5-mini, text-embedding-3-large) apply unless
        # the user overrides them in .env.
        llm_api_key=_env("LLM_API_KEY") or _env("OPENAI_API_KEY"),
        llm_provider=_env("LLM_PROVIDER"),
        llm_model=_env("LLM_MODEL"),
        llm_endpoint=_env("LLM_ENDPOINT"),
        embedding_provider=_env("EMBEDDING_PROVIDER"),
        embedding_model=_env("EMBEDDING_MODEL"),
        embedding_endpoint=_env("EMBEDDING_ENDPOINT"),
        embedding_dimensions=_env("EMBEDDING_DIMENSIONS"),
        huggingface_tokenizer=_env("HUGGINGFACE_TOKENIZER"),
        data_root=data_root,
        system_root=system_root,
        default_dataset=_env("MEMBERRY_DATASET", "memberry"),
        host=_env("MEMBERRY_HOST", "127.0.0.1"),
        port=int(_env("MEMBERRY_PORT", "8765") or "8765"),
        max_file_bytes=max_kb * 1024,
    )


def apply_to_cognee(settings: Settings) -> None:
    """Push MEMBERRY settings into the Cognee library.

    Isolating every Cognee configuration call here keeps the rest of the
    codebase decoupled from Cognee's evolving config surface.
    """
    import cognee

    settings.data_root.mkdir(parents=True, exist_ok=True)
    settings.system_root.mkdir(parents=True, exist_ok=True)

    cognee.config.data_root_directory(str(settings.data_root))
    cognee.config.system_root_directory(str(settings.system_root))

    # Forward LLM + embedding settings into the environment Cognee (LiteLLM)
    # reads. setdefault means anything already exported / in .env wins, and
    # empty values are skipped so Cognee's own defaults still apply.
    forwarded = {
        # Single-user CLI: disable Cognee 1.x multi-tenant access control so
        # calls don't require an authenticated user context.
        "ENABLE_BACKEND_ACCESS_CONTROL": "false",
        "LLM_API_KEY": settings.llm_api_key,
        "LLM_PROVIDER": settings.llm_provider,
        "LLM_MODEL": settings.llm_model,
        "LLM_ENDPOINT": settings.llm_endpoint,
        "EMBEDDING_PROVIDER": settings.embedding_provider,
        "EMBEDDING_MODEL": settings.embedding_model,
        "EMBEDDING_ENDPOINT": settings.embedding_endpoint,
        "EMBEDDING_DIMENSIONS": settings.embedding_dimensions,
        "HUGGINGFACE_TOKENIZER": settings.huggingface_tokenizer,
    }
    for key, value in forwarded.items():
        if value:
            os.environ.setdefault(key, value)

    if settings.llm_api_key:
        try:
            cognee.config.set_llm_api_key(settings.llm_api_key)
        except Exception:  # pragma: no cover - older/newer cognee variations
            pass
