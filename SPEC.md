# MEMBERRY — Technical Spec

## 1. Problem

AI coding agents lose all codebase context between sessions. They re-read
files repeatedly, exhaust context windows, and cannot reason about
cross-file structure (call graphs, dependencies). MEMBERRY provides a
persistent, queryable memory of a repository that any agent can read.

## 2. Goals (MVP)

- Ingest a local repo into a Cognee hybrid graph + vector store.
- Recall natural-language answers and structured insights from that store.
- Expose recall via both CLI and HTTP so agents can integrate easily.
- Run in minutes, no Docker, stdlib-only CLI.

### Non-goals (MVP)

- Real-time/incremental re-indexing on file change.
- Multi-repo cross-linking, auth on the HTTP server, hosted deployment.
- A VS Code extension UI (docs show manual wiring instead).

## 3. Architecture

```
+-----------+      +------------+      +-----------------------+
|  repo     | ---> | ingest.py  | ---> | Cognee dataset        |
|  files    |      | (crawl)    |      | remember()            |
+-----------+      +------------+      +-----------+-----------+
                                                   |
                                       hybrid graph + vector store
                                                   |
+-----------+      +------------+      +-----------v-----------+
|  agent    | <--- | recall.py  | <--- | Cognee recall()       |
|           |      | serve.py   |      | (auto-routed)         |
+-----------+      +------------+      +-----------------------+
```

The **only** modules that import `cognee` are `config.py`, `ingest.py`,
`recall.py`, and `lifecycle.py`. This keeps the integration surface small
and swappable. Cognee is imported lazily inside functions so the CLI loads
(and `--help`/parser tests run) without it installed.

## 4. Components

### 4.1 `src/config.py`
- `Settings` (frozen dataclass) built from env via `load_settings()`.
- `apply_to_cognee(settings)` configures data/system roots and forwards LLM +
  embedding settings (including `ENABLE_BACKEND_ACCESS_CONTROL=false`).
- Owns the include-extension and exclude-dir default lists.

### 4.2 `src/ingest.py`
- `iter_source_files(repo, settings)` — generator yielding ingestable files;
  filters excluded dirs, non-source extensions, oversized and binary files.
- `ingest_repo(repo_path, settings, dataset)` — async; collects files
  (each prefixed with `# FILE: <relpath>` for provenance) and hands the batch
  to `cognee.remember()` in one call.
- Returns `IngestResult(repo, dataset, files_ingested, files_skipped, bytes_ingested)`.

### 4.3 `src/recall.py`
- `recall(query, settings, mode, dataset)` — async; calls `cognee.recall()`
  (auto-routed unless a mode is given), normalises results to text, and reads
  a missing dataset as "no memory" instead of raising.
- Returns `RecallResult(query, mode, dataset, answer, raw)`.
- Modes: `auto` (default), `answer`/`graph`, `rag`, `chunks`, `triplets`,
  `summaries`, `code`, `lucky`.

### 4.4 `src/lifecycle.py`
- `improve_memory(settings, dataset)` → `cognee.improve()`.
- `forget_memory(settings, dataset, everything)` → `cognee.forget()`.

### 4.5 `src/serve.py`
- `create_app(settings)` → FastAPI app.
- Endpoints: `GET /health`, `GET|POST /recall`, `POST /ingest`,
  `POST /improve`, `POST /forget`.
- `run(host, port)` boots Uvicorn.

### 4.6 `src/cli_utils.py`
- `quiet_logging()` / `verbose_logging()` — control Cognee log noise.
- `spinner(message)` — TTY-only progress indicator.

### 4.7 `memberry.py`
- argparse CLI: `ingest`, `recall`, `improve`, `forget`, `serve`; `--json`
  on `ingest`/`recall`, `--verbose` on all. Translates the Kuzu single-writer
  lock error into a friendly message.

## 5. Data model

- **Dataset** = a named Cognee namespace (default `memberry`). One repo per
  dataset is the recommended convention.
- **Document** = one source file's text, prefixed with its repo-relative path.
- Cognee derives entities/relationships during `remember`.

## 6. Configuration

Environment variables (see `.env.example`, which ships OpenAI / OpenRouter+
fastembed / Ollama profiles): `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`,
`LLM_ENDPOINT`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `MEMBERRY_HOME`,
`MEMBERRY_DATA_DIR`, `MEMBERRY_SYSTEM_DIR`, `MEMBERRY_DATASET`,
`MEMBERRY_MAX_FILE_KB`, `MEMBERRY_HOST`, `MEMBERRY_PORT`.

## 7. Testing

`tests/` covers MEMBERRY-owned logic offline (no network): settings defaults,
file filtering, oversized-file skipping, mode mapping, result stringification,
and CLI parsing. Extra checks (SearchType drift, graceful missing-dataset
recall) run automatically when Cognee is installed.

## 8. Risks / open questions

- **Cognee API drift.** Search-type enum and config helpers vary by version;
  mitigated by isolating all Cognee calls and a test that validates modes
  against the installed `SearchType`.
- **Single-writer graph store.** Cognee's Kuzu backend allows one writer;
  `ingest`/`improve`/`forget` must not run while `serve` holds the store.
- **Cost/latency** of `remember` on large repos — bounded by file-size and
  extension filters; incremental ingest is future work.
- **Provenance fidelity** — current approach prepends file paths; a richer
  Cognee code-graph pipeline is a stretch goal.

## 9. Stretch goals

- Incremental re-ingest / `watch` daemon driven by file changes.
- `query_type=CODING_RULES` / Cognee code-graph pipeline for call-graph awareness.
- Per-repo auto dataset naming and a `list` command.
- MCP server wrapper so agents discover MEMBERRY as a tool automatically.
