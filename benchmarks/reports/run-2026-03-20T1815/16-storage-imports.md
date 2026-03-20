# Query 16: What files import from `storage.py` and what do they use?

**Category:** Dependencies
**Arrow tool:** `trace_dependencies`
**Timestamp:** 2026-03-20T18:15

---

## Round 1 — Traditional Tools

**Tools used:** Grep (4 calls), Bash (2 timestamps)
**Tool calls:** 6 (4 substantive)
**Wall time:** 24,194 ms
**Estimated tokens read:** ~480 (120 lines x 4)

### Findings

Direct importers of `storage.py` (11 files found):

| File | Symbols imported |
|---|---|
| `src/arrow/server.py` | `Storage` (also lazy `Storage as _S` x2) |
| `src/arrow/indexer.py` | `Storage` |
| `src/arrow/search.py` | `ChunkRecord`, `Storage` |
| `src/arrow/cli.py` | `Storage` (lazy import) |
| `tests/test_core.py` | `Storage` |
| `tests/test_noncode_chunking.py` | `Storage` |
| `tests/test_edge_cases.py` | `Storage` |
| `tests/test_precision.py` | `Storage` |
| `benchmarks/bench.py` | `Storage` |
| `benchmarks/bench_comparison.py` | `Storage` |
| `demo_comparison.py` | `Storage` |

**Missed:** `tests/test_server.py` (imports Storage indirectly or via conftest, not caught by direct grep pattern).

**Quality:** 4/5 — Found specific symbols per file (ChunkRecord vs Storage), but missed one importer and provided no transitive dependency info.
**Precision:** 90%

---

## Round 2 — Arrow Tools

**Tools used:** `trace_dependencies` (1 call)
**Tool calls:** 1
**Wall time:** 11,221 ms
**Tokens returned:** ~450

### Findings

- **12 direct importers** identified (including `tests/test_server.py` that grep missed)
- **What storage.py imports:** `__future__`, `sqlite3`, `time`, `dataclasses`, `pathlib`, `typing`, `re`
- **Transitive importers (depth 2):** 26+ additional files that indirectly depend on storage.py via server.py, indexer.py, search.py, and cli.py
- **Missing:** Does not report which specific symbols each file imports (e.g., `Storage` vs `ChunkRecord`)

**Quality:** 4/5 — More complete importer list with transitive dependencies, but lacks per-file symbol detail.
**Precision:** 95%

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Tool calls | 4 | 1 |
| Wall time (ms) | 24,194 | 11,221 |
| Tokens consumed | ~480 | ~450 |
| Direct importers found | 11/12 | 12/12 |
| Specific symbols per file | Yes | No |
| Transitive dependencies | No | Yes (depth 2) |
| Quality | 4/5 | 4/5 |
| Precision | 90% | 95% |

## Verdict

**Arrow wins on completeness and speed** (2.2x faster, found all 12 importers vs 11, plus full transitive graph). **Traditional wins on symbol-level detail** (knows exactly which names each file imports: `Storage` vs `ChunkRecord`). For dependency analysis, Arrow provides the better starting point — the transitive importer graph is extremely valuable and would require many additional grep rounds to replicate manually. Ideally, combining both approaches (Arrow for the graph, one grep for symbol specifics) gives the fullest picture.
