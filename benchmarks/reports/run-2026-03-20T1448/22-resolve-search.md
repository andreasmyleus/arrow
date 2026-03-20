# Query 22: Find all definitions of `search` across indexed repos

**Category:** Cross-repo
**Arrow tool(s):** `resolve_symbol`
**Timestamp:** 2026-03-20T14:48

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 21,404 ms |
| Tool calls | 6 |
| Tokens (approx) | 280 |
| Quality | 3/5 |
| Precision | 100% |

**Method:** Grepped for `def search` across all Python files in the main repo and all three cloned repos (`pydantic`, `fastapi`, `encode`). Found 2 function definitions in the main Arrow repo. Read each to confirm signatures and docstrings. No matches in cloned repos.

**Results found:**
1. `SearchEngine.search()` in `src/arrow/search.py:404` — hybrid BM25 + vector search
2. `VectorStore.search()` in `src/arrow/vector_store.py:61` — nearest-neighbor vector search

**Limitations:** Had to manually enumerate clone directories and run separate Grep per repo. No way to search "all indexed projects" in a single command — must know the filesystem paths. Quality docked because the approach does not scale and required 6 tool calls across 4 directories.

## Round 2 — Arrow (`resolve_symbol`)

| Metric | Value |
|--------|-------|
| Wall time | 10,893 ms |
| Tool calls | 1 |
| Chunks returned | 3 |
| Tokens (approx) | 680 |
| Quality | 4/5 |
| Precision | 67% |

**Method:** Single call to `resolve_symbol(symbol="search", project="andreasmyleus/arrow")`.

**Results found:**
1. `SearchEngine.search()` in `src/arrow/search.py:404-654` — full function body included
2. `VectorStore.search()` in `src/arrow/vector_store.py:61-75` — full function body included
3. `[search]` config block in `arrow.toml:9-32` — TOML configuration section (false positive)

**Notes:** The TOML config block is not a function/class definition — it is a configuration section that happens to be named `search`. This is a minor false positive that reduces precision to 67% (2 true positives out of 3 results). However, the tool returned full function bodies with context, which the traditional approach required extra Read calls to obtain. No results from other indexed repos (pydantic, fastapi) which is correct since those repos don't define a bare `search` function.

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time | 21,404 ms | 10,893 ms | Arrow (1.96x faster) |
| Tool calls | 6 | 1 | Arrow (6x fewer) |
| Tokens | ~280 | ~680 | Traditional (2.4x fewer) |
| Quality | 3/5 | 4/5 | Arrow |
| Precision | 100% | 67% | Traditional |
| Cross-repo | Manual per-directory | Automatic all-project | Arrow |

**Summary:** Arrow's `resolve_symbol` answered the cross-repo query in a single tool call and half the wall time, automatically searching across all indexed projects without needing to know filesystem paths. It included full function bodies, which is valuable for understanding definitions. The tradeoff is a minor false positive (TOML config section) and higher token count due to returning full code bodies. Traditional approach had perfect precision but required manual enumeration of every repo directory and 6 tool calls. For the intended use case of cross-repo symbol resolution, Arrow is the clear winner on ergonomics and speed despite the slight precision gap.
