# Query 04: Error Handling Patterns

**Query:** "Review error handling patterns across the codebase — where are errors caught, logged, or swallowed?"
**Category:** get_context — Architecture
**Arrow tool under test:** `get_context`

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774012295046
**End:** 1774012324035
**Duration:** 28,989 ms (~29s)
**Tool calls:** 11 (1 Glob + 10 Grep with context)
**Estimated tokens:** ~3,200 lines x 4 = ~12,800 tokens

### Findings

Identified **5 distinct error handling patterns** across 14 source files:

#### 1. Silent Swallowing (`except ...: pass`)
The most common anti-pattern. Errors are caught and discarded with no logging:
- `storage.py:299` — old metadata read failure silently ignored
- `storage.py:374` — FTS5 rebuild failure silently ignored
- `server.py:299-300` — git root detection falls back silently
- `server.py:1072-1073` — git root detection falls back silently
- `server.py:1083-1084` — TypeError on last_indexed check silently ignored
- `tools_github.py:115-116` — index existence check fails silently
- `tools_github.py:205-206` — project rename conflict silently ignored
- `tools_github.py:225-226` — post-clone verification silently ignored
- `vector_store.py:58-59` — vector removal failure silently ignored

#### 2. Logged + Degraded (`except ...: logger.warning/exception + fallback`)
Errors are logged and the system degrades gracefully:
- `server.py:152-153` — background re-index logged via `logger.exception`, lock released
- `server.py:307-308` — auto-index logged, returns JSON error to caller
- `server.py:1119-1120` — auto-warm logged via `logger.exception`
- `search.py:472-473` — vector search fails, falls back to BM25 only
- `indexer.py:66-67` — embedding generation logged via `logger.exception`
- `indexer.py:144-146` — file hash failure logged, increments error counter, continues
- `indexer.py:157-159` — file read failure logged, increments error counter, continues
- `embedder.py:129-131` — model load logged via `logger.exception`, returns False
- `chunker.py:521-523` — tree-sitter parse error logged, returns empty list
- `vector_store.py:39-40` — index load warned, starts fresh

#### 3. Returned as JSON Error (user-facing)
Errors are caught and returned as structured error messages:
- `server.py:558-559` — invalid regex returns `{"error": "Invalid regex: ..."}`
- `tools_github.py:170-174` — `gh` CLI not found returns install hint
- `tools_github.py:175-178` — clone timeout returns suggestion for sparse paths
- `tools_data.py:217-218` — invalid JSON bundle returns error message

#### 4. Specific Exception Types (targeted catches)
- `git_utils.py` — consistently catches `(CalledProcessError, FileNotFoundError, TimeoutExpired)` tuples, returns None
- `discovery.py:179,188` — catches `OSError` for file stat/read failures, continues iteration
- `chunker.py:284,298,305` — catches `(AttributeError, TypeError)` for tree-sitter API compatibility
- `storage.py:770` — catches `re.error` for invalid regex patterns

#### 5. Explicit Raises (preconditions)
- `embedder.py:173` — `raise RuntimeError("Embedder not loaded")` if used before `load()`
- `embedder.py:224` — same pattern for `embed_query`

### Notable: `tools_analysis.py` has zero try/except blocks — all analysis tools let exceptions propagate.

**Quality:** 5/5 — comprehensive review of all error handling across every source file
**Precision:** 95% — all findings are directly relevant error handling patterns

---

## Round 2 — Arrow (`get_context`)

**Start:** 1774012327295
**End:** 1774012338275
**Duration:** 10,980 ms (~11s)
**Tool calls:** 1
**Tokens returned:** 0 (no results)
**Chunks returned:** 0

### Findings

`get_context` returned **no results** for this query. The tool's relevance-based retrieval could not match the abstract/architectural nature of "error handling patterns" to any specific code chunks. This is a cross-cutting concern that spans many files and doesn't map to specific function names or code patterns.

**Quality:** 0/5 — no results returned
**Precision:** N/A — nothing to evaluate

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Duration | 29.0s | 11.0s |
| Tool calls | 11 | 1 |
| Tokens used | ~12,800 | 0 |
| Quality | 5/5 | 0/5 |
| Precision | 95% | N/A |
| Completeness | Full coverage of 14 files | No results |

## Verdict

**Traditional wins decisively.** This query exposes a fundamental limitation of `get_context`: it cannot answer cross-cutting architectural questions about patterns that span the entire codebase. Error handling is not a "chunk" — it is a pattern distributed across every file. Grep-based approaches (searching for `except`, `logger.error`, `raise`) are the natural fit for this kind of structural/pattern review query. Arrow's semantic search has no single chunk that is "about" error handling, so relevance filtering correctly (but unhelpfully) returns nothing.

This is a category where `search_regex` would be the appropriate Arrow tool, not `get_context`.
