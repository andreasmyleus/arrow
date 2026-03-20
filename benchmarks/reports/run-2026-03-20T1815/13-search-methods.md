# Query 13: Find all methods named `search`

**Category:** Symbol lookup
**Query:** "Find all methods named `search`"
**Arrow tool:** `search_structure`

## Round 1 — Traditional (Glob + Grep + Read)

- **Duration:** 7,621 ms
- **Tool calls:** 2 (2x Grep)
- **Tokens read:** ~144 (36 lines of grep output)
- **Strategy:** `grep "def search\b"` across all Python files, first for file matches, then with context (`-A 3`) for signatures.

### Results

| # | Location | Description |
|---|----------|-------------|
| 1 | `src/arrow/vector_store.py:61` | `VectorStore.search(self, query_vector, limit=50)` |
| 2 | `src/arrow/search.py:404` | `SearchEngine.search(self, query, limit=10, ...)` |

Also returned 3 false positives: string literals in `tests/test_core.py`, `tests/test_precision.py`, and `demo_comparison.py` containing `"def search"` as data, not actual definitions.

- **Quality:** 4/5 — Found both real methods correctly; false positives required manual filtering.
- **Precision:** 40% (2 true results out of 5 returned lines)

## Round 2 — Arrow (`search_structure`)

- **Duration:** 10,308 ms
- **Tool calls:** 1 (`search_structure(symbol="search", kind="any")`) — note: first attempt with `kind="method"` returned empty (Arrow indexes these as `function` kind), requiring a retry with `kind="any"`.
- **Tokens returned:** ~2,500 (full source code of all 3 results including the 250-line `SearchEngine.search`)

### Results

| # | Location | Description |
|---|----------|-------------|
| 1 | `src/arrow/vector_store.py:61-75` | `VectorStore.search()` — with full 15-line source |
| 2 | `src/arrow/search.py:404-654` | `SearchEngine.search()` — with full 250-line source |
| 3 | `arrow.toml:9-32` | `[search]` config section (false positive) |

- **Quality:** 4/5 — Found both real methods with full source code. One false positive (TOML config section). The `kind="method"` filter did not work (returns empty), requiring `kind="any"` which includes non-method results.
- **Precision:** 67% (2 true method results out of 3 returned)

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 7,621 ms | 10,308 ms |
| Tool calls | 2 | 1 (2 attempts) |
| Tokens consumed | ~144 | ~2,500 |
| Results found | 2/2 | 2/2 |
| False positives | 3 | 1 |
| Precision | 40% | 67% |
| Quality | 4/5 | 4/5 |

## Analysis

**Traditional wins on speed and token efficiency.** Grep was faster (7.6s vs 10.3s) and far more token-efficient (~144 vs ~2,500 tokens). The traditional approach required manual filtering of string-literal false positives but returned compact results.

**Arrow wins on precision** (67% vs 40%) since AST-based indexing avoids string-literal false positives. However, Arrow returned significantly more tokens because it includes full source code for each match -- the 250-line `SearchEngine.search()` method inflated the response substantially.

**Notable issue:** Arrow's `kind="method"` filter returned no results, even though both `search` definitions are class methods. They are indexed as `kind="function"`, requiring a broader `kind="any"` search that also pulls in config sections. This is a correctness gap in the structure index -- Python methods inside classes should be indexed with `kind="method"`.

**Winner:** Traditional (marginally) -- for simple symbol-name lookups, Grep is faster, cheaper, and sufficient. Arrow's main advantage (full source code) is offset by the token cost and the method/function kind misclassification.
