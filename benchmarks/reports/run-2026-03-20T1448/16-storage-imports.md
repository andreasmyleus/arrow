# Query 16: What files import from `storage.py` and what do they use?

**Category:** Dependencies
**Arrow tool(s):** `trace_dependencies`

## Round 1 — Traditional (Glob + Grep + Read)

**Duration:** 19,257 ms (1774010984346 -> 1774011003603)
**Tool calls:** 6 (1 Grep broad search + 4 targeted Greps + 1 Grep for storage.py own imports)
**Lines returned:** ~95 lines of grep matches
**Estimated tokens:** ~380

### Findings

**Direct importers (source):**
| File | Imports |
|------|---------|
| `src/arrow/search.py` | `ChunkRecord, Storage` |
| `src/arrow/indexer.py` | `Storage` |
| `src/arrow/cli.py` | `Storage` (lazy) |
| `src/arrow/server.py` | `Storage`, plus 2 lazy `Storage as _S` |

**Direct importers (tests):**
| File | Imports |
|------|---------|
| `tests/test_edge_cases.py` | `Storage` |
| `tests/test_core.py` | `Storage` |
| `tests/test_precision.py` | `Storage` |
| `tests/test_noncode_chunking.py` | `Storage` |

**Direct importers (benchmarks/demos):**
| File | Imports |
|------|---------|
| `benchmarks/bench.py` | `Storage` |
| `benchmarks/bench_comparison.py` | `Storage` |
| `demo_comparison.py` | `Storage` |

**Indirect users (via `_get_storage()` from server.py):**
- `tools_analysis.py` — 30+ usages of `storage.*` methods (get_file, get_chunks_for_file, get_callers_of_symbol, etc.)
- `tools_data.py` — 25+ usages (list_projects, find_dead_code, store_memory, recall_memory, etc.)
- `tools_github.py` — 8 usages (get_project_by_name, create_project, etc.)

**storage.py own imports:** `sqlite3`, `time`, `dataclasses.dataclass`, `pathlib.Path`, `typing.Optional`

### Assessment
- Found 11 direct importers plus 3 indirect heavy users via `_get_storage()`.
- Required multiple grep passes to distinguish direct vs indirect usage.
- Could not determine transitive dependency tree without further manual work.

**Quality: 4/5** — Complete direct import picture but transitive graph required extra effort.
**Precision: 90%** — All findings accurate; missed `tests/test_server.py` (imports indirectly).

---

## Round 2 — Arrow (`trace_dependencies`)

**Duration:** 8,041 ms (1774011007425 -> 1774011015466)
**Tool calls:** 1
**Chunks returned:** structured JSON (no chunk tokens, pure metadata)
**Estimated tokens:** ~250 (JSON response)

### Findings

**Direct importers (12 files):**
- `src/arrow/server.py`, `src/arrow/indexer.py`, `src/arrow/search.py`, `src/arrow/cli.py`
- `tests/test_core.py`, `tests/test_edge_cases.py`, `tests/test_noncode_chunking.py`, `tests/test_precision.py`, `tests/test_server.py`
- `benchmarks/bench.py`, `benchmarks/bench_comparison.py`, `demo_comparison.py`

**Transitive importers (depth 2):**
- Via `server.py`: 26 files including `tools_analysis.py`, `tools_data.py`, `tools_github.py`, `watcher.py`, and 20 test files
- Via `indexer.py`: 8 files including benchmarks and tests
- Via `cli.py`: `__main__.py`
- Via `search.py`: `vector_store.py` and 2 test files

**storage.py own imports:** `__future__`, `sqlite3`, `time`, `dataclasses`, `pathlib`, `typing`, `re`

### Assessment
- Single call returned both direct and transitive dependency graph to depth 2.
- Caught `tests/test_server.py` which the traditional round initially missed in the direct list.
- Also found `re` as an import that the traditional grep missed (likely a conditional or later import).
- Does not show *which symbols* each file imports (e.g., `ChunkRecord` vs `Storage`).

**Quality: 5/5** — Full dependency graph including transitive importers.
**Precision: 95%** — Comprehensive; only gap is per-file symbol detail.

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 19,257 ms | 8,041 ms |
| Tool calls | 6 | 1 |
| Tokens (est.) | ~380 | ~250 |
| Direct importers found | 11 | 12 |
| Transitive graph | Not attempted | 36 unique transitive files |
| Quality | 4/5 | 5/5 |
| Precision | 90% | 95% |

**Winner: Arrow**

Arrow's `trace_dependencies` returned a complete two-level dependency graph in a single call, including 12 direct importers and 36 transitive importers across 4 intermediate paths. The traditional approach required 6 tool calls and still missed one direct importer (`test_server.py`) and the entire transitive graph. Arrow was 2.4x faster and provided significantly richer structural information. The one advantage of the traditional approach is showing exactly which symbols each file imports (e.g., `ChunkRecord` vs `Storage`), which Arrow's output omits.
