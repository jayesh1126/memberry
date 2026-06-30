#!/usr/bin/env python3
"""MEMBERRY — codebase memory for AI coding agents.

CLI entrypoint, exposed as the ``memberry`` console command. Examples:

    memberry doctor
    memberry ingest --repo /path/to/repo [--dataset NAME]
    memberry recall "what does the auth module do?" [--mode answer]
    memberry serve [--host 127.0.0.1] [--port 8765]

Uses only the standard library (``argparse``) for the CLI surface so the
tool stays trivial to install and run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .cli_utils import quiet_logging, spinner, verbose_logging
from .config import load_settings
from .doctor import format_checks, run_doctor
from .ingest import ingest_repo
from .lifecycle import forget_memory, improve_memory
from .recall import DEFAULT_MODE, recall
from .update import update_memory, watch_repo


def _cmd_ingest(args: argparse.Namespace) -> int:
    """Handle ``memberry ingest``."""
    settings = load_settings()
    with spinner("Ingesting repo into memory...", enabled=not args.verbose):
        result = asyncio.run(ingest_repo(args.repo, settings, dataset=args.dataset))
    if args.json:
        print(json.dumps(result.__dict__, indent=2))
    else:
        print(
            f"Ingested {result.files_ingested} file(s) "
            f"({result.bytes_ingested:,} bytes, {result.files_skipped} skipped) "
            f"into dataset '{result.dataset}'."
        )
    return 0


def _cmd_recall(args: argparse.Namespace) -> int:
    """Handle ``memberry recall``."""
    settings = load_settings()
    with spinner("Recalling...", enabled=not args.verbose):
        result = asyncio.run(
            recall(args.query, settings, mode=args.mode, dataset=args.dataset)
        )
    if args.json:
        print(json.dumps(
            {"query": result.query, "mode": result.mode,
             "dataset": result.dataset, "answer": result.answer},
            indent=2,
        ))
    else:
        print(result.answer)
    return 0


def _cmd_improve(args: argparse.Namespace) -> int:
    """Handle ``memberry improve`` — enrich/sharpen existing memory."""
    settings = load_settings()
    with spinner("Improving memory...", enabled=not args.verbose):
        dataset = asyncio.run(improve_memory(settings, dataset=args.dataset))
    print(f"Improved memory for dataset '{dataset}'.")
    return 0


def _cmd_forget(args: argparse.Namespace) -> int:
    """Handle ``memberry forget`` — delete a dataset (or everything)."""
    settings = load_settings()
    with spinner("Forgetting...", enabled=not args.verbose):
        target = asyncio.run(
            forget_memory(settings, dataset=args.dataset, everything=args.all)
        )
    scope = "all datasets" if target == "*" else f"dataset '{target}'"
    print(f"Forgot {scope}.")
    return 0


def _summarize_update(result) -> str:
    """One-line summary of an UpdateResult."""
    how = "rebuilt" if result.rebuilt else "incremental"
    return (
        f"dataset '{result.dataset}' ({how}): "
        f"+{len(result.added)} new, ~{len(result.modified)} changed, "
        f"-{len(result.removed)} removed"
    )


def _cmd_update(args: argparse.Namespace) -> int:
    """Handle ``memberry update`` — sync memory with current repo state."""
    settings = load_settings()
    with spinner("Updating memory...", enabled=not args.verbose):
        result = asyncio.run(
            update_memory(args.repo, settings, dataset=args.dataset, full=args.full)
        )
    if not result.changed and not args.full:
        print(f"Memory for dataset '{result.dataset}' is already up to date.")
    else:
        print(f"Updated {_summarize_update(result)}.")
    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    """Handle ``memberry watch`` — keep memory in sync as files change."""
    settings = load_settings()
    print(
        f"Watching {args.repo} every {args.interval:g}s "
        f"(dataset '{args.dataset or settings.default_dataset}'). Ctrl+C to stop."
    )
    try:
        watch_repo(
            args.repo, settings, dataset=args.dataset,
            interval=args.interval, full=args.full,
            on_update=lambda r: print(f"  [updated] {_summarize_update(r)}"),
        )
    except KeyboardInterrupt:
        print("\nStopped watching.")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    """Handle ``memberry serve``."""
    from .serve import run

    run(host=args.host, port=args.port)
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Handle ``memberry doctor`` — preflight the environment and providers."""
    settings = load_settings()
    with spinner("Running checks...", enabled=not args.verbose):
        checks = asyncio.run(run_doctor(settings, live=not args.offline))
    print(format_checks(checks))
    return 0 if all(c.ok for c in checks) else 1


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the MEMBERRY CLI."""
    parser = argparse.ArgumentParser(
        prog="memberry",
        description="Codebase memory for AI coding agents, powered by Cognee.",
    )
    # Shared flags available on every subcommand (e.g. `recall ... --verbose`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show full Cognee logs instead of clean output",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", parents=[common], help="Preflight environment + provider checks")
    p_doctor.add_argument("--offline", action="store_true", help="Skip live LLM/embedding checks")
    p_doctor.set_defaults(func=_cmd_doctor)

    p_ingest = sub.add_parser("ingest", parents=[common], help="Ingest a repo into memory")
    p_ingest.add_argument("--repo", required=True, help="Path to the repository root")
    p_ingest.add_argument("--dataset", default=None, help="Dataset/namespace name")
    p_ingest.add_argument("--json", action="store_true", help="Emit JSON output")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_recall = sub.add_parser("recall", parents=[common], help="Recall context from memory")
    p_recall.add_argument("query", help="Natural-language question about the repo")
    p_recall.add_argument(
        "--mode", default=DEFAULT_MODE,
        help="auto|answer|graph|rag|chunks|triplets|summaries|code|lucky",
    )
    p_recall.add_argument("--dataset", default=None, help="Dataset/namespace name")
    p_recall.add_argument("--json", action="store_true", help="Emit JSON output")
    p_recall.set_defaults(func=_cmd_recall)

    p_update = sub.add_parser("update", parents=[common], help="Sync memory with changed files")
    p_update.add_argument("--repo", required=True, help="Path to the repository root")
    p_update.add_argument("--dataset", default=None, help="Dataset/namespace name")
    p_update.add_argument("--full", action="store_true", help="Force a full rebuild")
    p_update.set_defaults(func=_cmd_update)

    p_watch = sub.add_parser("watch", parents=[common], help="Auto-sync memory as files change")
    p_watch.add_argument("--repo", required=True, help="Path to the repository root")
    p_watch.add_argument("--dataset", default=None, help="Dataset/namespace name")
    p_watch.add_argument("--interval", type=float, default=3.0, help="Poll interval seconds (default 3)")
    p_watch.add_argument("--full", action="store_true", help="Force full rebuild on each change")
    p_watch.set_defaults(func=_cmd_watch)

    p_improve = sub.add_parser("improve", parents=[common], help="Enrich/sharpen existing memory")
    p_improve.add_argument("--dataset", default=None, help="Dataset/namespace name")
    p_improve.set_defaults(func=_cmd_improve)

    p_forget = sub.add_parser("forget", parents=[common], help="Delete a dataset's memory")
    p_forget.add_argument("--dataset", default=None, help="Dataset/namespace name")
    p_forget.add_argument("--all", action="store_true", help="Wipe ALL datasets")
    p_forget.set_defaults(func=_cmd_forget)

    p_serve = sub.add_parser("serve", parents=[common], help="Run the HTTP recall server")
    p_serve.add_argument("--host", default=None, help="Bind host (default from env)")
    p_serve.add_argument("--port", type=int, default=None, help="Bind port (default 8765)")
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the chosen subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Quiet by default for clean output; --verbose restores full Cognee logs.
    # Must run before the command imports Cognee so LOG_LEVEL takes effect.
    verbose_logging() if args.verbose else quiet_logging()

    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        # Cognee's graph store (Kuzu) is single-writer; a running server or an
        # orphaned worker holds the lock. Explain instead of dumping a trace.
        if "lock" in str(exc).lower():
            print(
                "error: memory is locked by another MEMBERRY process "
                "(is `serve` running?). Stop it and retry.",
                file=sys.stderr,
            )
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
