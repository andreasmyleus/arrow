# Query 10 — Find All Environment Variable Reads

**Category:** Regex
**Query:** "Find all environment variable reads"
**Arrow tool(s):** `search_regex` with pattern `os\.environ|getenv|ARROW_`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 8,284 ms |
| Tool calls | 1 |
| Tokens (est.) | ~332 (~83 matching lines x 4) |
| Quality | 5/5 |
| Precision | 88% |

### Answer

Single Grep call with pattern `os\.environ|getenv|ARROW_` returned 83 matching lines across 20+ files. Results grouped by category:

**Source code (real env var reads):**
- **src/arrow/server.py** — 6 `os.environ.get` calls for `ARROW_DB_PATH` and `ARROW_VECTOR_PATH` across init, SSE, and stdio entry points (lines 65-66, 76-77, 138-139, 1085-1089, 1154)
- **src/arrow/cli.py** — 2 reads (`os.environ.get`) and 2 writes (`os.environ[...]`) for DB and vector paths (lines 31-32, 48, 50)

**Infrastructure/config:**
- **Dockerfile** (lines 33-34): `ENV ARROW_DB_PATH=/data/index.db`, `ENV ARROW_VECTOR_PATH=/data/vectors.usearch`
- **docker-compose.yml** (lines 10-11): Same env vars in compose config
- **arrow.toml** (line 47): Documents env var precedence

**Demo scripts:**
- **demo_part2.py** — 5 occurrences (set + get)
- **demo_comparison.py** — 1 occurrence (set)

**Tests (fixture setup/teardown):**
- conftest.py, test_auto_warm.py, test_server.py, test_tool_chain.py, test_diff_context.py, test_search_regex.py, test_doc_search.py — all set/pop `ARROW_DB_PATH` and `ARROW_VECTOR_PATH`
- test_precision.py, test_search_regex.py — synthetic test data containing `os.environ.get` patterns

**Noise (precision loss):**
- Benchmark report markdown files from prior runs matched `ARROW_` in prose descriptions — not actual env var reads

### Method
One Grep call was sufficient. The multi-pattern regex `os\.environ|getenv|ARROW_` captured all relevant matches in a single pass. No file reading was needed since Grep returned content with line numbers.

---

## Round 2 — Arrow (`search_regex`)

| Metric | Value |
|---|---|
| Wall time | N/A (tool denied) |
| Tool calls | 1 (denied) |
| Tokens (est.) | 0 |
| Chunks returned | 0 |
| Quality | N/A |
| Precision | N/A |

### Notes

The `search_regex` MCP tool call was denied by the permission system. No results were returned. This round cannot be scored.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 8,284 ms | N/A (denied) |
| Tool calls | 1 | 1 (denied) |
| Tokens consumed | ~332 | 0 |
| Quality | 5/5 | N/A |
| Precision | 88% | N/A |

### Verdict

**Traditional wins by default** — the Arrow tool was denied permission and returned no results.

The traditional approach was highly efficient for this query: a single Grep call with the same regex pattern produced comprehensive results. This is the ideal query type for Grep since the regex pattern is known in advance and the task is a literal pattern scan rather than a semantic search. Grep returned line-level matches with file paths and line numbers, which is exactly what `search_regex` would have provided.

Precision was 88% rather than 100% because the `ARROW_` component of the regex matched occurrences in benchmark report markdown files that describe env vars in prose, rather than actual code-level env var reads.

**Note:** This comparison is invalid due to the Arrow tool denial. A fair re-run would be needed to draw conclusions about Arrow's `search_regex` performance on this query.
