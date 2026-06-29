#!/usr/bin/env python3
"""End-to-end MEMBERRY demo for judges (cross-platform).

Ingests the bundled sample repo, runs a few recall questions, and sharpens
the memory with an improve pass. Run from anywhere:

    python scripts/demo.py

Requires dependencies installed and a configured .env (see .env.example).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_REPO = ROOT / "examples" / "demo_repo"
DATASET = "demo_run"


def run(*args: str) -> int:
    """Invoke the MEMBERRY CLI with the active interpreter and echo the call."""
    print(f"\n$ memberry {' '.join(args)}\n" + "-" * 60)
    return subprocess.run(
        [sys.executable, str(ROOT / "memberry.py"), *args], cwd=ROOT
    ).returncode


def main() -> int:
    steps = [
        ("Ingest the sample repo",
         ["ingest", "--repo", str(DEMO_REPO), "--dataset", DATASET]),
        ("Recall: what the auth module does",
         ["recall", "what does the auth module do?", "--dataset", DATASET]),
        ("Recall: cross-file dependency",
         ["recall", "what does charge_user depend on?", "--dataset", DATASET]),
        ("Improve: sharpen the memory",
         ["improve", "--dataset", DATASET]),
    ]

    print("=== MEMBERRY end-to-end demo ===")
    for title, args in steps:
        print(f"\n### {title}")
        if run(*args) != 0:
            print(f"\nStep failed: {title}", file=sys.stderr)
            return 1

    print(
        f"\nDone. Ask your own question:\n"
        f'  python memberry.py recall "<your question>" --dataset {DATASET}\n'
        f"Clean up with:\n"
        f"  python memberry.py forget --dataset {DATASET}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
