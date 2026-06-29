"""Presentation helpers for the MEMBERRY CLI.

Two small concerns kept out of the command logic:

- :func:`quiet_logging` silences Cognee and its dependencies so the CLI
  prints results, not a wall of logs (with a ``--verbose`` escape hatch).
- :func:`spinner` shows a lightweight progress indicator on a TTY while a
  slow async call runs, and no-ops when output is piped.
"""

from __future__ import annotations

import itertools
import logging
import os
import sys
import threading
import time
import warnings
from contextlib import contextmanager
from typing import Iterator

# Chatty third-party loggers that flood the terminal during ingest/recall.
_NOISY_LOGGERS = (
    "cognee", "dotenv", "aiohttp", "asyncio", "litellm", "LiteLLM",
    "httpx", "httpcore", "alembic", "sqlalchemy", "fastembed",
)


def quiet_logging() -> None:
    """Silence Cognee/dependency log noise for clean CLI output.

    Sets ``LOG_LEVEL=ERROR`` (which Cognee honours) and pins chatty loggers
    to CRITICAL. Call before Cognee is imported so it takes effect on import.
    """
    os.environ.setdefault("LOG_LEVEL", "ERROR")
    warnings.filterwarnings("ignore", category=ResourceWarning)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.CRITICAL)


def verbose_logging() -> None:
    """Opt back into full Cognee logs (the ``--verbose`` flag)."""
    os.environ["LOG_LEVEL"] = "INFO"


@contextmanager
def spinner(message: str, enabled: bool = True) -> Iterator[None]:
    """Animate a spinner on stderr while the wrapped block runs.

    No-ops when disabled or when stderr is not a TTY, so ``--json`` and
    piped output stay clean.
    """
    if not enabled or not sys.stderr.isatty():
        yield
        return

    stop = threading.Event()

    def _spin() -> None:
        for frame in itertools.cycle("|/-\\"):
            if stop.is_set():
                break
            sys.stderr.write(f"\r{frame} {message}")
            sys.stderr.flush()
            time.sleep(0.1)
        sys.stderr.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stderr.flush()

    worker = threading.Thread(target=_spin, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join()
