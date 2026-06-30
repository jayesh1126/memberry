# Wiring MEMBERRY into AI coding agents

MEMBERRY exposes recall over HTTP, so any agent that can make an HTTP request
(or run a shell command) can use it as persistent codebase memory.

Start the server first:

```bash
memberry ingest --repo .        # remember the current repo
memberry serve --port 8765      # http://localhost:8765
```

---

## Generic HTTP contract

```
POST http://localhost:8765/recall
Content-Type: application/json

{ "query": "how does auth issue tokens?", "mode": "answer" }
```

Response:

```json
{ "query": "...", "mode": "answer", "dataset": "memberry", "answer": "..." }
```

---

## Claude Code

Claude Code can call MEMBERRY through a shell command. Add a note to your
project's `CLAUDE.md` so the agent knows the tool exists:

```md
## Codebase memory
Before exploring unfamiliar code, query MEMBERRY for context:
`memberry recall "<question>"`
(or `curl localhost:8765/recall?query=<question>` if the server is running)
```

For tighter integration, expose MEMBERRY as an MCP server (stretch goal) so
Claude Code discovers a `recall` tool automatically.

---

## Cline (VS Code)

Cline supports custom instructions and can run terminal commands. Add to your
Cline rules / `.clinerules`:

```
When you need background on this repo, run:
  memberry recall "<your question>" --json
and use the "answer" field before reading files manually.
```

If you prefer HTTP, point Cline at `http://localhost:8765/recall`.

---

## Aider

Aider works from the shell. Pull context into your prompt:

```bash
CTX=$(memberry recall "where is rate limiting handled?")
aider --message "Context from MEMBERRY:\n$CTX\n\nNow add a per-IP limit."
```

---

## Tips

- **One repo per dataset.** Use `--dataset myrepo` to keep projects separate.
- **Re-ingest after big changes.** The MVP does not auto-watch files.
- **Pick the right mode.** `auto` (default) lets Cognee route; `answer` for
  prose, `triplets` for raw entity/relationship reasoning, `chunks` for
  verbatim source snippets.
- **Don't write while serving.** Cognee's graph store is single-writer, so
  avoid running `ingest`/`improve`/`forget` while `serve` is live.
