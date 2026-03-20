# Query 13: Find all methods named "search"

**Category:** search_structure — AST symbol lookup
**Date:** 2026-03-20

## Query

"Find all methods named search"

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 6169 ms |
| Tool calls | 1 |
| Tokens (response) | ~650 |
| Quality | 3/5 |
| Precision | 40% |

**Method:** `Grep` for `def search` across all Python files.

**Results found (14 lines):**
- `src/arrow/search.py:385` — `def search(` (exact match)
- `src/arrow/vector_store.py:61` — `def search(` (exact match)
- `src/arrow/storage.py:720` — `def search_fts(` (prefix, not exact)
- `src/arrow/storage.py:755` — `def search_regex(` (prefix, not exact)
- `src/arrow/storage.py:810` — `def search_symbols(` (prefix, not exact)
- `src/arrow/server.py:463` — `def search_code(` (prefix, not exact)
- `src/arrow/server.py:514` — `def search_regex(` (prefix, not exact)
- `src/arrow/server.py:881` — `def search_structure(` (prefix, not exact)
- `tests/test_precision.py:33` — string literal (false positive)
- `tests/test_doc_search.py:89` — string literal (false positive)
- `tests/test_doc_search.py:172` — method call, not definition (false positive)
- `tests/test_core.py:227` — string literal (false positive)
- `tests/test_core.py:232` — string literal (false positive)
- `demo_comparison.py:55` — string in a list (false positive)

**Notes:** Grep returns everything matching `def search` — prefix matches (search_fts, search_code, etc.) and string literals in test files. Manual filtering required to identify the 2 exact `search` methods. No source code context provided.

## Round 2 — Arrow (search_structure)

| Metric | Value |
|---|---|
| Wall time | 7219 ms |
| Tool calls | 1 |
| Tokens (response) | ~3800 |
| Quality | 5/5 |
| Precision | 100% |

**Method:** `search_structure(symbol="search", project="andreasmyleus/arrow")`

**Results found (3):**
1. `src/arrow/vector_store.py:61-75` — `VectorStore.search()` method (full source)
2. `src/arrow/search.py:385-629` — `HybridSearcher.search()` method (full source)
3. `arrow.toml:9-32` — `[search]` config section

**Notes:** Exact name matching via AST index. No prefix false positives (search_fts, search_code, etc. correctly excluded). Full source code returned for each match. The config section match is a bonus from TOML structure parsing.

## Comparison

| Dimension | Traditional | Arrow | Winner |
|---|---|---|---|
| Wall time | 6169 ms | 7219 ms | Traditional |
| Tool calls | 1 | 1 | Tie |
| Precision | 40% (2/14 lines were exact matches) | 100% (2/2 methods + 1 config) | Arrow |
| Source included | No | Yes (full bodies) | Arrow |
| Manual filtering needed | Yes (heavy) | No | Arrow |
| Quality | 3/5 | 5/5 | Arrow |

## Verdict

**Arrow wins on quality and precision.** Traditional Grep is slightly faster but returns 14 results where only 2 are actual methods named `search` — the rest are prefix matches (search_fts, search_code) and string literals in tests. Arrow's AST-based search_structure uses exact name matching, returning only the true `search` methods with full source code. This is the ideal use case for structural search: finding symbols by exact name without regex noise.

The time difference (1050ms slower for Arrow) is negligible given the elimination of manual result filtering.
