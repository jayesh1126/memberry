#!/usr/bin/env python3
"""MEMBERRY — codebase memory for AI coding agents.

CLI entrypoint. Three subcommands:

    python memberry.py ingest --repo /path/to/repo [--dataset NAME]
    python memberry.py recall "what does the auth module do?" [--mode answer]
    python memberry.py serve [--host 127.0.0.1] [--port 8765]

Uses only the standard library (``argparse``) for the CLI surface so the
tool stays trivial to install and run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.cli_utils import quiet_logging, spinner, verbose_logging
from src.config import load_settings
from src.ingest import ingest_repo
from src.lifecycle import forget_memory, improve_memory
from src.recall import DEFAULT_MODE, recall


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


def _cmd_serve(args: argparse.Namespace) -> int:
    """Handle ``memberry serve``."""
    from src.serve import run

    run(host=args.host, port=args.port)
    return 0


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
