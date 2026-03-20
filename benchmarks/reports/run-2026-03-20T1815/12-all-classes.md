# Query 12: Find all classes in the codebase

**Category:** Symbol lookup
**Query:** "Find all classes in the codebase"
**Arrow tool:** `search_structure` with `kind="class"`

## Round 1 — Traditional Tools

**Method:** `Grep` with pattern `^class \w+` on `src/arrow/*.py`

| Metric | Value |
|--------|-------|
| Wall time | 5,787 ms |
| Tool calls | 1 (Grep) |
| Tokens (est.) | ~72 (18 lines x 4) |
| Quality | 3/5 |
| Precision | 70% |

**Findings:** Found 18 classes in 8 files under `src/arrow/`. The grep only searched `src/arrow/` Python files, missing test classes entirely. Also would miss indented class definitions (nested classes). No source code or line ranges included — just file:line:match.

**Classes found (18):**
- `_IndexHandler`, `FileWatcher` (watcher.py)
- `Embedder` (embedder.py)
- `SearchResult`, `QueryClassification`, `HybridSearcher` (search.py)
- `ProjectRecord`, `FileRecord`, `ChunkRecord`, `SymbolRecord`, `ImportRecord`, `Storage` (storage.py)
- `Indexer` (indexer.py)
- `VectorStore` (vector_store.py)
- `Chunk` (chunker.py)
- `SearchConfig`, `IndexConfig`, `ArrowConfig` (config.py)

## Round 2 — Arrow Tools

**Method:** `search_structure(symbol="*", kind="class", project="andreasmyleus/arrow")`

| Metric | Value |
|--------|-------|
| Wall time | 13,067 ms |
| Tool calls | 1 (search_structure) |
| Tokens (est.) | ~3,500 (large JSON with source snippets) |
| Quality | 5/5 |
| Precision | 100% |

**Findings:** Found 68 classes across both `src/arrow/` (18 production classes) and `tests/` (50 test classes). Each result includes name, kind, file, line range, and source code snippet. Covers nested classes (e.g., `Inner` in test_edge_cases.py) and non-Python class definitions found in test fixtures (e.g., JavaScript `MyClass`).

**Production classes (18):** Same 18 as traditional round.
**Test classes (50):** All `Test*` classes across 17 test files, plus fixture classes like `Inner` and `MyClass`.

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time | 5,787 ms | 13,067 ms | Traditional |
| Tool calls | 1 | 1 | Tie |
| Tokens consumed | ~72 | ~3,500 | Traditional |
| Completeness | 18/68 classes (26%) | 68/68 classes (100%) | Arrow |
| Source included | No | Yes | Arrow |
| Line ranges | No | Yes | Arrow |
| Nested classes | No | Yes | Arrow |
| Quality | 3/5 | 5/5 | Arrow |
| Precision | 70% | 100% | Arrow |

## Verdict

**Arrow wins on completeness and richness; Traditional wins on speed and token efficiency.**

The traditional grep approach was faster and lighter on tokens, but only found classes in the `src/arrow/` directory — a conscious scoping choice that missed all 50 test classes. The grep pattern `^class` also cannot find nested/indented class definitions. Extending the grep to all `.py` files and indented patterns would have required additional tool calls and more tokens.

Arrow's `search_structure` with `symbol="*"` and `kind="class"` returned a complete enumeration of all 68 classes across the entire indexed codebase in a single call, with source code snippets and line ranges. The tradeoff is significantly more tokens (~3,500 vs ~72) and slower wall time (13s vs 6s). However, the token cost is justified by the much richer data returned — each class comes with its source definition, which eliminates follow-up `Read` calls.

For a "find all classes" enumeration task, Arrow provides a definitively complete answer in one call. The traditional approach requires careful scoping decisions and multiple grep passes to achieve similar coverage.
