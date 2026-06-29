# 🫐 MEMBERRY

**Codebase memory for AI coding agents.**

MEMBERRY ingests a software repository into a [Cognee](https://www.cognee.ai/)
hybrid **graph + vector** memory store, then exposes **recall** over both a
CLI and an HTTP API so AI coding agents (Cline, Claude Code, Aider) can keep
persistent, queryable context about your codebase *across sessions* — instead
of re-reading the whole repo every time.

> Built for the **WeMakeDevs × Cognee Hackathon** (Jun 29 – Jul 5, 2026).

---

## Why

AI coding agents are amnesiacs. Every new session they re-scan files, blow
context windows, and forget the architecture you explained yesterday.
MEMBERRY gives them a brain: ingest once, recall forever.

- **Graph + vector, not just RAG.** Cognee builds entities and relationships
  (which module calls which, who depends on whom), so recall understands
  *structure*, not just text similarity.
- **Agent-ready.** One HTTP endpoint any agent can call.
- **Minutes to run.** Pure-Python, stdlib CLI, no Docker required.

---

## Quickstart

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure (only LLM_API_KEY is required)
cp .env.example .env && $EDITOR .env

# 3. Ingest a repo into memory
python memberry.py ingest --repo ./examples/demo_repo

# 4. Recall context
python memberry.py recall "how does billing know which user to charge?"

# 5. Or serve it over HTTP for your agent
python memberry.py serve --port 8765
```

---

## CLI

MEMBERRY maps directly onto Cognee's memory **lifecycle** — `remember`,
`recall`, `improve`, `forget`:

| Command | Cognee lifecycle | What it does |
| --- | --- | --- |
| `python memberry.py ingest --repo PATH [--dataset NAME]` | `remember()` | Crawl a repo and build its memory graph |
| `python memberry.py recall "QUESTION" [--mode MODE]` | `recall()` | Ask a question about the ingested repo |
| `python memberry.py update --repo PATH [--dataset NAME]` | `remember()`/`forget()` | Sync memory with changed files (incremental) |
| `python memberry.py watch --repo PATH [--interval N]` | `remember()`/`forget()` | Auto-sync memory as you edit — *living memory* |
| `python memberry.py improve [--dataset NAME]` | `improve()` | Enrich/sharpen memory so recall gets better over time |
| `python memberry.py forget [--dataset NAME] [--all]` | `forget()` | Delete a dataset (or wipe everything) |
| `python memberry.py serve [--host H] [--port P]` | — | Start the HTTP recall server |

Add `--json` to `ingest`/`recall` for machine-readable output, or `--verbose`
to any command for full Cognee logs.

### Living memory (`update` / `watch`)

Code changes, so memory must too. MEMBERRY tracks a per-dataset manifest of
file hashes and only re-touches Cognee when something actually changed:

```bash
python memberry.py update --repo .         # sync after edits (no-op if unchanged)
python memberry.py watch  --repo .         # keep memory fresh automatically
```

`update` re-`remember`s new files incrementally; when files are modified or
removed it rebuilds the dataset so recall never surfaces stale code. `watch`
runs that on a timer — edit a file, and the agent's memory follows.

### Recall modes

`recall` defaults to `auto`, letting Cognee route each query between semantic
similarity and graph traversal. Override with `--mode`:

| Mode | Returns |
| --- | --- |
| `auto` (default) | Cognee auto-routes the best strategy per query |
| `answer` / `graph` | Natural-language answer grounded in the graph |
| `rag` | Answer grounded in raw chunks |
| `chunks` | Raw matching text chunks |
| `triplets` | Entity / relationship reasoning |
| `summaries` | Node summaries |
| `code` | Code-oriented rules / conventions |
| `lucky` | Let Cognee decide everything |

---

## HTTP API

Start with `python memberry.py serve`. Then:

```bash
# Health
curl localhost:8765/health

# Recall (GET)
curl "localhost:8765/recall?query=which%20module%20issues%20tokens"

# Recall (POST)
curl -X POST localhost:8765/recall \
  -H 'content-type: application/json' \
  -d '{"query": "what does the auth module do?", "mode": "answer"}'

# Ingest (POST)
curl -X POST localhost:8765/ingest \
  -H 'content-type: application/json' \
  -d '{"repo": "./examples/demo_repo"}'

# Update after edits (POST)
curl -X POST localhost:8765/update \
  -H 'content-type: application/json' \
  -d '{"repo": "./examples/demo_repo"}'
```

Full endpoint set: `GET /health`, `GET|POST /recall`, `POST /ingest`,
`POST /update`, `POST /improve`, `POST /forget`. Interactive docs at `/docs`.

Interactive docs at `http://localhost:8765/docs`.

See [docs/integrations.md](docs/integrations.md) to wire MEMBERRY into Cline,
Claude Code, and Aider.

---

## How it works

```
repo files ──► ingest.py ──► cognee.remember()
                                     │
                           hybrid graph + vector store
                                     │
agent ◄── recall.py / serve.py ◄── cognee.recall()
```

1. **Ingest** crawls the repo, skips noise (`.git`, `node_modules`, binaries,
   oversized files), tags each file with its path, and hands the batch to
   `cognee.remember()` — which chunks, extracts entities/relationships,
   embeds, and builds the graph in one call.
2. **Recall** calls `cognee.recall()` with auto-routing (semantic vs graph)
   and returns a normalised answer.

All Cognee-specific calls live in `src/config.py`, `src/ingest.py`,
`src/recall.py`, and `src/lifecycle.py`, so upgrading the memory layer
touches one place.

---

## Configuration

Everything is environment-driven (see [`.env.example`](.env.example), which
ships three ready profiles: OpenAI, OpenRouter + local embeddings, and
Ollama). Key vars: `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`,
`EMBEDDING_PROVIDER`, `MEMBERRY_DATASET`, `MEMBERRY_PORT`.

---

## Development

```bash
pip install -r requirements.txt pytest
pytest                      # offline tests need no API key / network
```

The offline tests cover MEMBERRY's own logic (config, file filtering, mode
mapping, result shaping, CLI parsing). A few extra checks run automatically
when Cognee is installed.

---

## Project layout

```
memberry/
├── memberry.py          # CLI entrypoint (argparse)
├── src/
│   ├── config.py        # env settings + Cognee config (single integration point)
│   ├── ingest.py        # repo crawl + cognee.remember()
│   ├── recall.py        # cognee.recall() wrapper
│   ├── lifecycle.py     # cognee.improve() / forget()
│   ├── update.py        # incremental update + watch daemon (living memory)
│   ├── manifest.py      # per-dataset file-hash manifests
│   ├── serve.py         # FastAPI HTTP server
│   └── cli_utils.py     # quiet logging + progress spinner
├── tests/               # offline unit tests
├── examples/demo_repo/  # tiny sample repo for the demo
├── docs/integrations.md # wire into Cline / Claude Code / Aider
└── scripts/             # end-to-end demo for judges
```

## License

MIT.
