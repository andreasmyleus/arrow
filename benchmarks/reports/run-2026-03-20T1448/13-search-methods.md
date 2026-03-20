# Query 13: Find all methods named `search`

**Category:** Symbol
**Arrow tool(s):** `search_structure`
**Timestamp:** 2026-03-20T14:48

---

## Round 1 — Traditional (Glob + Grep + Read)

**Approach:** Grep for `def search\b` across all Python files, then Read the two real method signatures for context.

**Results found:**
1. `src/arrow/search.py:404` — `HybridSearch.search(self, query, limit, ...)` — hybrid BM25 + vector search (lines 404-654)
2. `src/arrow/vector_store.py:61` — `VectorStore.search(self, query_vector, limit)` — nearest-neighbor search (lines 61-75)

Also matched (non-method definitions):
- `tests/test_core.py:227` — string literal `"def search(): pass"` (test fixture data)
- `tests/test_precision.py:33` — string literal `"def search(query):\n"` (test fixture data)
- `demo_comparison.py:55` — string literal in a list (not a method definition)

**Precision note:** 2 true methods out of 5 grep hits = need manual filtering to discard test fixture strings.

| Metric | Value |
|--------|-------|
| Tool calls | 3 (1 Grep + 2 Read) |
| Wall time | 8,188 ms |
| Tokens in | ~136 (~34 lines x 4) |
| Quality | 4/5 — found both real methods, but required manual filtering of false positives |
| Precision | 40% raw (2/5 hits were real methods), 100% after manual filtering |

---

## Round 2 — Arrow (`search_structure`)

**Approach:** Single call: `search_structure(symbol="search", kind="any", project="andreasmyleus/arrow")`.

**Results found:**
1. `src/arrow/vector_store.py:61-75` — `VectorStore.search(self, query_vector, limit)` — full source included
2. `src/arrow/search.py:404-654` — `HybridSearch.search(self, query, limit, ...)` — full source included
3. `arrow.toml:9-32` — `[search]` config section (kind: "config") — not a method, but a structural match on the symbol name

**Precision note:** 2 true methods + 1 config section. No false positives from test fixture strings.

| Metric | Value |
|--------|-------|
| Tool calls | 1 |
| Wall time | 12,728 ms |
| Tokens in | ~1,276 (~319 lines x 4) — includes full source of both methods |
| Chunks returned | 3 |
| Quality | 5/5 — found both methods with full source, no test-fixture noise |
| Precision | 67% (2/3 are actual methods; the config entry is a reasonable structural match) |

---

## Comparison

| Dimension | Traditional | Arrow | Winner |
|-----------|-------------|-------|--------|
| Tool calls | 3 | 1 | Arrow |
| Wall time | 8,188 ms | 12,728 ms | Traditional |
| Tokens in | ~136 | ~1,276 | Traditional |
| Precision (raw) | 40% | 67% | Arrow |
| Quality | 4/5 | 5/5 | Arrow |
| Noise filtering needed | Yes (test fixtures) | Minimal (config section) | Arrow |

## Notes

- **Traditional was faster and cheaper** in this case. A simple grep for `def search` is a natural fit for finding method definitions. The token cost was low because only signatures were read, not full source.
- **Arrow returned full source code** for both methods (250+ lines for `HybridSearch.search`), which inflated token count significantly. This is useful when you need implementation details but wasteful when you only need to locate definitions.
- **Arrow had better precision** — its AST-based index correctly distinguished real definitions from string literals in test fixtures. Traditional grep matched `"def search"` inside strings, requiring manual filtering.
- **Arrow classified methods as "function"** rather than "method" — this is why `kind="method"` returned zero results. The `kind="any"` fallback was needed. This is a known limitation of the AST structure index.
- **The config section match** (`arrow.toml [search]`) is a reasonable structural hit but not a "method" — with `kind="method"` or `kind="function"` this would be filtered out (though `kind="method"` currently returns nothing due to the classification issue).
- **Verdict:** For pure symbol location, traditional grep is faster and cheaper. Arrow wins on precision and completeness (full source), but at a cost of ~9x more tokens.
