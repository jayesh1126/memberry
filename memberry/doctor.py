"""Preflight checks for MEMBERRY (``memberry doctor``).

Validates the environment and provider configuration — and optionally
live-tests the LLM and embedding connections — *before* a costly ingest, so
misconfiguration (wrong model slug, missing key, broken embeddings) surfaces
in seconds instead of mid-pipeline.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

from .config import Settings, apply_to_cognee


@dataclass
class Check:
    """Result of a single preflight check."""

    name: str
    ok: bool
    detail: str = ""


def _short(exc: Exception) -> str:
    """First line of an exception message, trimmed for a tidy report."""
    text = str(exc).strip()
    first = text.splitlines()[0] if text else type(exc).__name__
    return first[:160]


def _check_python() -> Check:
    major, minor = sys.version_info[:2]
    ok = (3, 10) <= (major, minor) <= (3, 14)
    hint = "" if ok else " (Cognee needs Python 3.10-3.14)"
    return Check("Python version", ok, f"{platform.python_version()}{hint}")


def _check_cognee() -> Check:
    try:
        import cognee

        return Check("Cognee installed", True, f"v{getattr(cognee, '__version__', '?')}")
    except Exception:  # noqa: BLE001
        return Check("Cognee installed", False, "run: pip install -e .")


def _describe_config(settings: Settings) -> Check:
    detail = (
        f"LLM={settings.llm_model or '(cognee default)'} "
        f"[{settings.llm_provider or 'openai'} @ {settings.llm_endpoint or 'default'}], "
        f"embeddings={settings.embedding_model or '(cognee default)'} "
        f"[{settings.embedding_provider or 'openai'}], "
        f"dataset='{settings.default_dataset}'"
    )
    return Check("Configuration", True, detail)


def _check_api_key(settings: Settings) -> Check:
    ok = bool(settings.llm_api_key)
    return Check("LLM API key", ok, "present" if ok else "set LLM_API_KEY in .env")


def _check_storage(settings: Settings) -> Check:
    try:
        settings.system_root.mkdir(parents=True, exist_ok=True)
        probe = settings.system_root / ".memberry_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return Check("Storage writable", True, str(settings.system_root))
    except OSError as exc:
        return Check("Storage writable", False, _short(exc))


async def _check_llm() -> Check:
    try:
        from cognee.infrastructure.llm.utils import test_llm_connection

        await test_llm_connection()
        return Check("LLM connection", True, "reachable")
    except Exception as exc:  # noqa: BLE001
        return Check("LLM connection", False, _short(exc))


async def _check_embeddings() -> Check:
    try:
        from cognee.infrastructure.llm.utils import test_embedding_connection

        await test_embedding_connection()
        return Check("Embedding connection", True, "reachable")
    except Exception as exc:  # noqa: BLE001
        return Check("Embedding connection", False, _short(exc))


async def run_doctor(settings: Settings, live: bool = True) -> list[Check]:
    """Run all preflight checks, returning them in display order.

    Live LLM/embedding checks run only when ``live`` is set and the basics
    (Cognee installed + API key present) pass, to avoid confusing failures.
    """
    checks = [
        _check_python(),
        _check_cognee(),
        _describe_config(settings),
        _check_api_key(settings),
        _check_storage(settings),
    ]

    cognee_ok = checks[1].ok
    key_ok = checks[3].ok
    if live and cognee_ok and key_ok:
        apply_to_cognee(settings)
        checks.append(await _check_llm())
        checks.append(await _check_embeddings())

    return checks


def format_checks(checks: list[Check]) -> str:
    """Render checks as an ASCII report with a final verdict line."""
    lines = [f"[{'ok' if c.ok else '!!'}] {c.name}: {c.detail}" for c in checks]
    failed = [c for c in checks if not c.ok]
    lines.append("")
    if failed:
        lines.append(f"{len(failed)} check(s) failed - fix the above before ingesting.")
    else:
        lines.append("All checks passed - ready to ingest.")
    return "\n".join(lines)
