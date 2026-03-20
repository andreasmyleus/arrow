# Query 16: What files import from storage.py and what do they use?

**Category:** trace_dependencies — Import graph

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 8,915 ms |
| Tool calls | 2 (Grep x2) |
| Quality | 3/5 |
| Precision | 75% |

### Method
Grepped for `from.*storage import` and `import storage` across all `.py` files in the codebase.

### Findings
13 import lines across 11 files:
- **src/arrow/search.py** — imports `ChunkRecord, Storage`
- **src/arrow/server.py** — imports `Storage` (top-level + 2 lazy imports as `_S`)
- **src/arrow/indexer.py** — imports `Storage`
- **src/arrow/cli.py** — imports `Storage` (lazy)
- **benchmarks/bench.py** — imports `Storage`
- **benchmarks/bench_comparison.py** — imports `Storage`
- **demo_comparison.py** — imports `Storage`
- **tests/test_core.py** — imports `Storage`
- **tests/test_precision.py** — imports `Storage`
- **tests/test_edge_cases.py** — imports `Storage`
- **tests/test_noncode_chunking.py** — imports `Storage`

### Limitations
- No transitive dependency info (who imports the importers)
- Missed `tests/test_server.py` (likely uses indirect import via conftest/server)
- Only shows direct import lines, no usage context

---

## Round 2 — Arrow (`trace_dependencies`)

| Metric | Value |
|---|---|
| Wall time | 10,928 ms |
| Tool calls | 1 |
| Quality | 5/5 |
| Precision | 95% |

### Method
Single call to `trace_dependencies(file="src/arrow/storage.py", depth=2)`.

### Findings
**Direct importers (12 files):**
- `src/arrow/server.py`
- `src/arrow/search.py`
- `src/arrow/indexer.py`
- `src/arrow/cli.py`
- `benchmarks/bench.py`
- `benchmarks/bench_comparison.py`
- `demo_comparison.py`
- `tests/test_core.py`
- `tests/test_edge_cases.py`
- `tests/test_noncode_chunking.py`
- `tests/test_precision.py`
- `tests/test_server.py`

**What storage.py itself imports:**
`__future__`, `annotations`, `sqlite3`, `time`, `dataclasses`, `pathlib`, `typing`, `re`

**Transitive importers (depth=2) — 26 additional files:**
- Via `server.py`: 20 files including all tool modules (`tools_analysis.py`, `tools_data.py`, `tools_github.py`), `watcher.py`, `conftest.py`, and 15 test files
- Via `indexer.py`: 8 files including benchmarks, demos, server, and tests
- Via `search.py`: 5 files including `vector_store.py` and test files
- Via `cli.py`: `__main__.py`

### Advantages
- Complete transitive dependency graph (2 levels deep)
- Found `tests/test_server.py` which Grep missed (indirect import)
- Shows both directions: what storage imports AND who imports storage
- Single tool call, structured JSON output

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 8,915 ms | 10,928 ms |
| Tool calls | 2 | 1 |
| Files found (direct) | 11 | 12 |
| Transitive importers | 0 | 26 |
| Quality | 3/5 | 5/5 |
| Precision | 75% | 95% |

### Summary
Arrow's `trace_dependencies` provided significantly richer results with a single tool call. While wall time was slightly higher, the output included the full 2-level transitive import graph (38 files total vs 11), both import directions, and caught an indirect importer that Grep missed. For dependency/import analysis, Arrow delivers substantially more actionable information with less effort.
