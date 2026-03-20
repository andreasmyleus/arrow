# Query 17: What does `search.py` depend on?

**Category:** Dependencies
**Arrow tool(s):** `trace_dependencies`
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

**Method:** Read the first 50 lines of `search.py` to capture all import statements. Then Grep across `src/arrow/` and `tests/` for `from .search import` / `from arrow.search import` to find reverse dependencies (who imports search.py).

**Results:**

Direct dependencies (imports by search.py):
- `__future__`, `logging`, `os`, `re`, `dataclasses`, `typing` (stdlib)
- `tiktoken` (third-party)
- `.chunker.decompress_content`, `.config.get_config`, `.storage.ChunkRecord`, `.storage.Storage`, `.vector_store.VectorStore` (internal)

Imported by (direct):
- `src/arrow/server.py`
- `src/arrow/cli.py`
- `tests/test_core.py`
- `tests/test_doc_search.py`
- `tests/test_edge_cases.py`
- `tests/test_noncode_chunking.py`
- `tests/test_precision.py`

**Limitations:** Only searched `src/arrow/` and `tests/` directories. Missed importers in `benchmarks/` and project root (demo scripts). No transitive dependency information.

| Metric | Value |
|--------|-------|
| Tool calls | 4 (Read + 2 Grep + verification Grep) |
| Wall time | 9,619 ms |
| Tokens (est.) | ~240 |
| Quality | 4/5 |
| Precision | 95% — all results correct, but incomplete scope |

---

## Round 2 — Arrow (`trace_dependencies`)

**Method:** Single call: `trace_dependencies(file="src/arrow/search.py", project="andreasmyleus/arrow", depth=2)`.

**Results:**

Direct dependencies: Same 4 internal modules + stdlib + tiktoken. Correctly identified.

Imported by (13 files listed):
- `benchmarks/bench.py` (correct)
- `benchmarks/bench_comparison.py` (correct)
- `demo_comparison.py` (correct)
- `src/arrow/cli.py` (correct)
- `src/arrow/server.py` (correct)
- `src/arrow/vector_store.py` — **FALSE POSITIVE**: vector_store.py does not import from search.py
- `tests/test_core.py` (correct)
- `tests/test_doc_search.py` (correct)
- `tests/test_edge_cases.py` (correct)
- `tests/test_noncode_chunking.py` (correct)
- `tests/test_precision.py` (correct)
- `tests/test_search_regex.py` — **FALSE POSITIVE**: imports from `arrow.server`, not `arrow.search`
- `tests/test_server.py` — **FALSE POSITIVE**: imports from `arrow.server`, not `arrow.search`

Transitive importers (depth 2): 26+ additional files that transitively depend on `search.py` via `server.py`, `vector_store.py`, and `cli.py`. This is valuable information the traditional approach did not attempt to gather.

| Metric | Value |
|--------|-------|
| Tool calls | 1 |
| Wall time | 7,397 ms |
| Tokens (est.) | ~320 |
| Quality | 3.5/5 |
| Precision | 77% (10/13 direct importers correct; 3 false positives) |

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Tool calls | 4 | 1 |
| Wall time (ms) | 9,619 | 7,397 |
| Tokens (est.) | ~240 | ~320 |
| Quality | 4/5 | 3.5/5 |
| Precision | 95% | 77% |
| Recall (direct importers) | 7/10 (70%) | 10/10 (100%) scope-wise, but 3 false |
| Transitive deps | No | Yes (depth 2) |

**Winner: Tie — each excels differently.**

**Analysis:**

Arrow is significantly more convenient (1 tool call vs 4) and faster (23% less wall time). It also provides transitive dependency information that the traditional approach did not attempt, which is genuinely useful for impact analysis.

However, Arrow has a notable precision problem: 3 of its 13 listed "imported_by" entries are false positives. `vector_store.py` does not import search.py at all, and `test_search_regex.py` / `test_server.py` import from `arrow.server`, not `arrow.search` directly. This appears to be a bug where the index conflates transitive dependencies with direct imports, or where keyword-based matching on the word "search" produces spurious results.

The traditional approach was more precise (all results verified correct) but had narrower scope — it only searched `src/arrow/` and `tests/`, missing legitimate importers in `benchmarks/` and the project root. This is a user error, not a tool limitation; additional Grep calls would have found them.

**Key takeaway:** `trace_dependencies` is the right tool for this query and provides excellent breadth, but the false positives in the `imported_by` list reduce trust. For high-stakes refactoring decisions, Arrow results should be verified with targeted Grep.
