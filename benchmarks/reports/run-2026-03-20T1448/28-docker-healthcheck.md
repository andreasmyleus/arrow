# Query 28: How does the healthcheck work in Docker?

**Category:** Needle
**Arrow tool(s) under test:** `get_context`

## Answer

The Docker healthcheck is defined in the `Dockerfile` (lines 40-41) using a `HEALTHCHECK` instruction:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/mcp')" || exit 1
```

It works as follows:
- **Interval:** Every 30 seconds, Docker runs the check command.
- **Timeout:** If the command takes longer than 5 seconds, it counts as a failure.
- **Start period:** Docker waits 10 seconds after container start before counting failures (grace period for startup).
- **Check command:** Uses Python's `urllib.request` to make an HTTP GET request to `http://localhost:8080/mcp`. If the MCP server endpoint responds (any 2xx status), the container is healthy. If the request fails or returns an error, `exit 1` marks the container as unhealthy.

The port 8080 matches the default configured in the `CMD` directive (`["--transport", "http", "--port", "8080"]`) and the `EXPOSE 8080` declaration.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 13,537 ms |
| Tool calls | 5 (Grep x2, Glob x1, Read x1, Grep x1) |
| Tokens (est.) | ~180 (45 lines Dockerfile) |
| Quality | 5/5 — complete answer with full context |
| Precision | 100% — found the exact HEALTHCHECK directive and related config |

**Steps:**
1. Grep for `HEALTHCHECK` + Glob for `Dockerfile*` + Grep for `healthcheck` (parallel) — found the Dockerfile immediately.
2. Read the full Dockerfile (45 lines) — HEALTHCHECK on lines 40-41, with CMD/EXPOSE context.
3. Grep in `server.py` for `/mcp|8080|health` — confirmed port default.

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall time | 8,326 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Quality | 1/5 — no results at all |
| Precision | 0% — complete miss |

**Notes:** `get_context` returned zero results. The Dockerfile is a non-code file; Arrow's indexer likely does not chunk Dockerfiles (or chunks them but the content does not match the query well enough to pass relevance thresholds). This is a known limitation for infrastructure/config file queries.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 13,537 ms | 8,326 ms |
| Tool calls | 5 | 1 |
| Quality | 5/5 | 1/5 |
| Precision | 100% | 0% |
| Tokens used | ~180 | 0 |

**Winner:** Traditional

**Why:** Arrow's index does not surface Dockerfile content for this query. The traditional approach found the answer immediately via straightforward grep for `HEALTHCHECK`. This is a category of query (infrastructure/config files) where keyword search on the filesystem is more reliable than semantic code search. Arrow would need to index non-code files like Dockerfiles and weight exact keyword matches (like "HEALTHCHECK") more heavily to handle this needle-in-a-haystack query.
