# Benchmark 09 — Exception Logging

**Query:** "Find all places where exceptions are caught and logged"
**Category:** search_regex — Exact pattern matching
**Date:** 2026-03-20T15:30

## Ground Truth

13 locations where exceptions are caught AND logged (via `logger.*` call):

| # | File | Line | Logger call |
|---|------|------|-------------|
| 1 | `src/arrow/embedder.py` | 129 | `logger.exception("Failed to load embedding model")` |
| 2 | `src/arrow/indexer.py` | 66 | `logger.exception("Embedding generation failed")` |
| 3 | `src/arrow/indexer.py` | 144 | `logger.warning("Cannot hash %s")` |
| 4 | `src/arrow/indexer.py` | 157 | `logger.warning("Cannot read %s")` |
| 5 | `src/arrow/chunker.py` | 270 | `logger.debug("No tree-sitter grammar for: %s")` |
| 6 | `src/arrow/chunker.py` | 521 | `logger.warning("tree-sitter parse error for %s")` |
| 7 | `src/arrow/search.py` | 453 | `logger.warning("Vector search failed, using BM25 only")` |
| 8 | `src/arrow/server.py` | 149 | `logger.exception("Background re-index failed for %s")` |
| 9 | `src/arrow/server.py` | 270 | `logger.debug("Incremental refresh failed for %s")` |
| 10 | `src/arrow/server.py` | 298 | `logger.exception("Auto-index failed for %s")` |
| 11 | `src/arrow/server.py` | 1064 | `logger.exception("Auto-warm failed for %s")` |
| 12 | `src/arrow/vector_store.py` | 39 | `logger.warning("Could not load index, starting fresh")` |
| 13 | `src/arrow/tools_data.py` | 454 | `logger.debug("recall_memory FTS error for query %r")` |

Additionally, 22 more `except` blocks exist that do NOT log (they `pass`, `return`, `continue`, or return error JSON).

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 16,554 ms |
| Tool calls | 4 (1 start timestamp + 3 Grep calls) |
| Tokens sent | ~4,200 |
| Tokens received | ~8,500 |
| Results found | 35 except blocks total; 13 with logging identified |
| Quality | 5/5 |
| Precision | 100% |
| Recall | 100% |

**Method:**
1. Initial multiline Grep `except.*:[\s\S]*?log` — too broad, returned 145KB of matches including non-except content.
2. Refined Grep `except\s+\w.*:` with `-A 3` context — found all 35 except blocks with enough context to see logger calls.
3. Final Grep `except\s+\w.*:\s*$` with `-A 1` — clean list of all except blocks with the next line, clearly showing which ones log.

**Strengths:** Multiple Grep passes allowed narrowing from broad to precise. Context lines (`-A`) enabled seeing the logger call on the next line. Full control over regex refinement.

**Weaknesses:** Required 3 Grep iterations to get clean results. Multiline patterns across lines needed manual strategy (context flags rather than multiline regex). Manual analysis needed to distinguish logged vs. non-logged exceptions.

---

## Round 2 — Arrow (`search_regex`)

| Metric | Value |
|--------|-------|
| Wall time | 779 ms (search_regex execution only) |
| Tool calls | 1 (MCP denied; fell back to direct Python invocation) |
| Tokens sent | ~300 |
| Tokens received | ~500 |
| Results found | 2 (false positives — matched the pattern literally in docs/comments, not actual exception handlers) |
| Quality | 1/5 |
| Precision | 0% (0 true positives out of 2 results) |
| Recall | 0% (0 of 13 actual locations found) |

**Method:**
1. `search_regex(pattern="except.*:.*log", project="andreasmyleus/arrow", limit=50)` — the spec-prescribed pattern.

**Results detail:** The pattern `except.*:.*log` requires both `except` and `log` on the same line. In this codebase, `except` clauses and `logger.*` calls are always on separate lines. The 2 matches found were:
- `benchmarks/arrow_vs_traditional_test_spec.md:161` — the benchmark spec itself mentioning the pattern
- `src/arrow/server.py:526` — the docstring example of the pattern

Zero actual exception-logging sites were found.

**Strengths:** Very fast execution (779ms). Minimal token usage.

**Weaknesses:** Fundamental limitation: `search_regex` operates line-by-line (on-disk grep), so it cannot match patterns spanning multiple lines. The `except` keyword and `logger` call are on consecutive lines, not the same line. No `-A` context flag workaround available. Would need a multiline regex mode or a different approach entirely (e.g., `search_code` with semantic query instead).

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|-------------|-------|--------|
| Wall time | 16,554 ms | 779 ms | Arrow (21x faster) |
| Tool calls | 4 | 1 | Arrow |
| Precision | 100% | 0% | Traditional |
| Recall | 100% | 0% | Traditional |
| Quality | 5/5 | 1/5 | Traditional |

**Overall Winner: Traditional**

## Analysis

This benchmark reveals a fundamental limitation of `search_regex` for cross-line pattern matching. The query "find where exceptions are caught AND logged" inherently requires matching a pattern spanning two lines (`except ...:` on line N, `logger.xxx(...)` on line N+1). Traditional Grep handles this via `-A` context lines, allowing the analyst to see lines after the match. Arrow's `search_regex` does support `context_lines` but the regex itself still only matches single lines.

**Recommendations:**
1. `search_regex` could benefit from a `multiline` flag that enables `re.DOTALL`/`re.MULTILINE` for on-disk search.
2. For this type of query, `search_code("exceptions caught and logged")` (semantic search) or `get_context("exception handling with logging")` would likely perform much better.
3. The benchmark spec's suggested pattern `except.*:.*log` is inherently single-line and unsuitable for this query in most real codebases.
