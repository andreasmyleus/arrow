# Query 13: Find all methods named "search"

**Category:** search_structure — Symbol
**Arrow tool under test:** `search_structure`
**Query:** "Find all methods named search"

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774012328173
**End:** 1774012341221
**Duration:** 13,048 ms

### Process
1. Grep for `def search\b` across all Python files — found 5 matches (2 real definitions + 3 test/string references).
2. Grep for `async def search\b` — no matches.
3. Read both real definition sites to confirm signatures and context.

### Results
Found 2 actual method definitions named `search`:

| # | File | Line | Class/Context |
|---|------|------|---------------|
| 1 | `src/arrow/vector_store.py` | 61 | `VectorStore.search(query_vector, limit)` — nearest neighbor search |
| 2 | `src/arrow/search.py` | 404 | `SearchEngine.search(query, limit, ...)` — hybrid BM25 + vector search |

Had to manually filter out 3 false positives from test files / string literals.

### Metrics
- **Tool calls:** 4 (2 Grep + 2 Read)
- **Estimated tokens:** ~2,500
- **Quality:** 4/5 — found both methods correctly, required manual filtering
- **Precision:** 100% (after filtering)

---

## Round 2 — Arrow (`search_structure`)

**Start:** 1774012343328
**End:** 1774012358977
**Duration:** 15,649 ms

### Process
1. Called `search_structure(symbol="search", kind="any", project="andreasmyleus/arrow")`.

### Results
Returned 3 results:

| # | File | Lines | Kind | Description |
|---|------|-------|------|-------------|
| 1 | `src/arrow/vector_store.py` | 61-75 | function | `VectorStore.search` — nearest neighbor search |
| 2 | `src/arrow/search.py` | 404-654 | function | `SearchEngine.search` — hybrid BM25 + vector search |
| 3 | `arrow.toml` | 9-32 | config | `[search]` config section |

Full source code included in response for all results.

### Metrics
- **Tool calls:** 1 (initial `kind="method"` returned empty; `kind="any"` found them — tree-sitter classifies Python methods as `function`)
- **Actual tool calls:** 2
- **Estimated tokens:** ~4,800 (full source of 250-line `SearchEngine.search` included)
- **Quality:** 4/5 — found both methods + bonus config section; methods labeled as "function" not "method"
- **Precision:** 67% (2 of 3 results are actual methods; the config section is a false positive for this query)

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 13,048 ms | 15,649 ms |
| Tool calls | 4 | 2 |
| Tokens (est.) | ~2,500 | ~4,800 |
| Quality | 4/5 | 4/5 |
| Precision | 100% | 67% |
| Results found | 2/2 | 2/2 (+1 config) |

## Notes

1. **Arrow returned `kind="method"` as empty** — tree-sitter indexes Python methods (def inside class) as `function`, not `method`. This is a known classification gap; the user must use `kind="any"` or `kind="function"` to find class methods.
2. **Token cost higher for Arrow** — the full 250-line `SearchEngine.search` source was included verbatim. Traditional approach only read 15 lines of context per match.
3. **Traditional required manual filtering** — grep matched string literals and test data; Arrow's AST-based approach avoided those false positives but introduced a config-section false positive instead.
4. **Arrow's single-call convenience** is offset here by the kind classification issue requiring a retry.
5. **Both approaches found the same 2 correct methods** — recall is equal at 100%.

## Verdict

**Slight edge: Traditional.** For this specific symbol search query, traditional grep was faster, used fewer tokens, and achieved higher precision. Arrow's AST index provides source code inline (useful for deeper analysis) but the `method` vs `function` kind classification and inclusion of config sections reduce precision. The approaches tie on recall.
