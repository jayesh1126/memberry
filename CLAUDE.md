# CLAUDE.md — Working Agreement

## Project
MEMBERRY — Codebase Memory for AI Coding Agents
Built for the WeMakeDevs × Cognee Hackathon (Jun 29 – Jul 5 2026)

## What this is
A Python CLI tool that ingests a software repo into a Cognee
hybrid graph-vector memory store, then exposes recall via CLI
and HTTP so AI coding agents (Cline, Claude Code, Aider) can
query persistent codebase context across sessions.


## Stack
- Language: Python 3.11+
- Memory layer: Cognee (open source, self-hosted)
- HTTP server: FastAPI + Uvicorn
- CLI: argparse (stdlib, no extra deps)
- Package manager: pip + requirements.txt
- No Docker required for MVP

## Project structure
memberry/
├── CLAUDE.md
├── SPEC.md
├── README.md
├── requirements.txt
├── memberry.py              ← CLI entrypoint
├── src/
│   ├── ingest.py         ← repo crawling + cognee.remember()
│   ├── recall.py         ← cognee.recall() wrapper
│   ├── lifecycle.py      ← cognee.improve() / forget()
│   ├── serve.py          ← FastAPI HTTP server
│   ├── cli_utils.py      ← quiet logging + spinner
│   └── config.py         ← env vars, settings
├── tests/
│   ├── test_recall.py   ← config, filtering, mode-mapping, recall logic
│   └── test_cli.py      ← CLI parsing + lifecycle wiring
├── examples/
│   └── demo_repo/        ← small sample repo for demo
├── docs/
│   └── integrations.md   ← how to wire into Cline / Claude Code
└── scripts/
    └── demo.py           ← runs end-to-end demo for judges (cross-platform)

## Principles
- Keep it simple — judges need to run this in minutes
- Every function has a docstring
- No global state
- Config via environment variables (.env), never hardcoded
- README is the product — if it's not in the README, it doesn't exist

## Commands to know
pip install -r requirements.txt
python memberry.py ingest --repo /path/to/repo
python memberry.py recall "what does the auth module do?"   # → cognee.recall()
python memberry.py improve                          # → cognee.improve()
python memberry.py forget --dataset memberry        # → cognee.forget()
python memberry.py serve --port 8765

## Cognee notes (verified against v1.2.2)
- Lifecycle API: remember / recall / improve / forget (all async).
- Default stores are embedded & local: SQLite + LanceDB + Kuzu (no server).
- Access control is ON by default; we set ENABLE_BACKEND_ACCESS_CONTROL=false.
- recall(auto_route=True) picks semantic-vs-graph automatically.
- SearchType has NO `INSIGHTS`; use TRIPLET_COMPLETION etc.