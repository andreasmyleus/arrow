# Query 28: How does the healthcheck work in Docker?

**Category:** Needle-in-Haystack
**Timestamp:** 2026-03-20T15:30

## Answer

The Docker healthcheck is defined in `/Users/andreas/arrow/Dockerfile` (line 40-41). It uses a Python one-liner to probe the MCP HTTP endpoint:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/mcp')" || exit 1
```

**How it works:**
- **Interval:** Runs every 30 seconds.
- **Timeout:** Each check must complete within 5 seconds.
- **Start period:** Waits 10 seconds after container start before counting failures (gives the server time to boot).
- **Probe:** Uses Python's `urllib.request` to make an HTTP GET to `http://localhost:8080/mcp`. If the request succeeds (HTTP 200), the container is healthy. If it fails (connection refused, timeout, non-200 status), `exit 1` marks the container as unhealthy.
- The endpoint `/mcp` is the MCP server's main endpoint, served on port 8080 as configured by the `CMD ["--transport", "http", "--port", "8080"]` entrypoint.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 7712 ms |
| Tool calls | 4 (Glob, Grep, Read, timestamp) |
| Files examined | 2 (Dockerfile, test_noncode_chunking.py via Grep) |
| Tokens in (est.) | ~2,800 |
| Tokens out (est.) | ~200 |
| Quality | 5/5 |
| Precision | 100% |

**Notes:** Glob found the Dockerfile immediately. Grep returned the HEALTHCHECK line with context from both the real Dockerfile and test fixtures. Read confirmed the full Dockerfile content. All information needed was obtained directly.

## Round 2 — Arrow (get_context)

| Metric | Value |
|---|---|
| Wall time | 5522 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens in (est.) | ~100 |
| Tokens out (est.) | ~50 |
| Quality | 0/5 |
| Precision | 0% |

**Notes:** Arrow returned no results. The Dockerfile is likely not indexed or the non-code chunker for Dockerfiles does not produce chunks that match this query well enough to pass relevance thresholds. The query got zero useful information.

## Comparison

| Dimension | Traditional | Arrow | Winner |
|---|---|---|---|
| Speed | 7.7s | 5.5s | Arrow (but no results) |
| Tool calls | 4 | 1 | Arrow |
| Quality | 5/5 | 0/5 | **Traditional** |
| Precision | 100% | 0% | **Traditional** |
| Completeness | Full Dockerfile + context | Nothing | **Traditional** |

**Winner: Traditional**

Arrow failed completely on this needle-in-haystack query. The Dockerfile healthcheck is a small, specific configuration detail. Traditional tools (Grep for HEALTHCHECK, Read for full file) found it instantly and precisely. Arrow's hybrid search returned zero results, likely because Dockerfile content is either not indexed or not well-represented in the vector/BM25 index for this type of query. This is a clear case where targeted keyword search (Grep) excels over semantic search.
