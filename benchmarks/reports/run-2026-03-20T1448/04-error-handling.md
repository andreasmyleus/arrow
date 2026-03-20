# Query 4: Error Handling Patterns

**Query:** "Review error handling patterns across the codebase — where are errors caught, logged, or swallowed?"
**Category:** Architecture
**Arrow tool(s) under test:** `get_context`
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 29,789 ms |
| Tool calls | 17 (3 Grep + 1 Glob + 13 Read) |
| Lines read | ~580 |
| Tokens (est.) | ~2,320 |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Identified **40+ except blocks** across 13 source files, falling into four distinct patterns:

1. **Log-and-continue (most common):** Exception is caught, logged via `logger.exception()` or `logger.warning()`, and execution continues with a fallback. Found in `server.py` (background re-index, auto-index, auto-warm), `indexer.py` (embedding generation), `embedder.py` (model load), `chunker.py` (tree-sitter parse), `search.py` (vector search fallback to BM25-only).

2. **Silent swallow (pass):** Exception caught with bare `pass` — no logging. Found in:
   - `storage.py:299-300` — reading old project metadata during migration
   - `storage.py:374-375` — FTS rebuild during migration
   - `storage.py:1299-1300` — recall_memory FTS query failure (returns empty)
   - `vector_store.py:58-59` — removing non-existent keys
   - `tools_github.py:115-116` — SHA freshness check
   - `tools_github.py:205-206` — project rename conflict
   - `tools_github.py:225-226` — remote commit verification
   - `server.py:290-291` — git root detection (falls back to cwd)
   - `server.py:1063-1064` — git root detection (falls back to cwd)
   - `server.py:1074-1075` — last_indexed type check
   - `chunker.py:284-285, 298-299` — tree-sitter API version compat

3. **User-facing error JSON:** Exception caught and returned as `{"error": "..."}` JSON string. Found in:
   - `server.py:549-550` — invalid regex
   - `tools_github.py:170-174` — `gh` CLI not found
   - `tools_github.py:175-179` — clone timeout
   - `tools_data.py:217-218` — invalid JSON bundle

4. **Graceful degradation with continue:** `OSError` caught during file I/O, increments error counter, skips file. Found in `indexer.py:144-147` (hash failure), `indexer.py:157-160` (read failure), `discovery.py:177-178, 186-187` (stat/binary check).

### Observations

- The codebase never uses bare `except:` (all catch specific types or `Exception`).
- Silent swallows are concentrated in non-critical paths (migrations, optional checks, API compat shims).
- `tools_github.py` has the most silent swallows (4 instances), all in optional verification steps.
- `storage.py` FTS search methods silently return empty results on failure (lines 752, 1066, 1299).

---

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall time | 14,007 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Quality | 1/5 |
| Precision | 0% |

### Findings

`get_context` returned **no results** for this query. The tool reported 127 files and 1,332 chunks indexed but found nothing relevant. The query is architectural/pattern-oriented ("where are errors caught, logged, or swallowed?") rather than targeting a specific symbol or keyword, which does not match well against code chunks via semantic or BM25 search.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 29,789 ms | 14,007 ms |
| Tool calls | 17 | 1 |
| Tokens consumed | ~2,320 | ~0 |
| Quality | 5/5 | 1/5 |
| Precision | 95% | 0% |
| Findings | 40+ except blocks, 4 patterns, 13 files | No results |

### Verdict

**Traditional wins decisively.** This is a structural/pattern-matching query that requires scanning for syntactic patterns (`except`, `pass`, `logger.error`) across the entire codebase. Grep-based tools are purpose-built for this. Arrow's semantic search could not surface any results because error handling is a cross-cutting concern distributed across many small code sites — no single chunk is "about" error handling. This query type is fundamentally outside the strengths of chunk-based retrieval and represents a category where traditional regex/grep search is the only viable approach.

### Arrow improvement opportunity

For pattern-audit queries, Arrow could benefit from a dedicated tool (e.g., `search_patterns` or `audit_patterns`) that scans all indexed chunks for syntactic patterns like `except.*pass`, or the existing `search_regex` tool could have been used instead. The `get_context` tool is not the right fit for this query type.
