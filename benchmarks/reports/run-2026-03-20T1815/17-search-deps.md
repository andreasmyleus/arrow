# Query 17: What does `search.py` depend on?

**Category:** Dependencies
**Arrow tool:** `trace_dependencies`
**Date:** 2026-03-20

## Query

"What does `search.py` depend on?"

## Traditional Round (Glob + Grep + Read)

**Method:** Read the top of `src/arrow/search.py` to extract import statements.

**Tools used:** 1 (Read)
**Time:** 4532 ms (1774009928405 → 1774009932937)
**Estimated tokens:** ~240 (60 lines x 4)

**Answer found:**

Standard library imports:
- `__future__.annotations`, `logging`, `os`, `re`, `dataclasses.dataclass`, `typing.Optional`

Third-party imports:
- `tiktoken`

Internal imports:
- `.chunker` → `decompress_content`
- `.config` → `get_config`
- `.storage` → `ChunkRecord`, `Storage`
- `.vector_store` → `VectorStore`

**Quality:** 4/5 — Correctly identifies all direct dependencies but gives no information about reverse dependencies (who imports search.py) or transitive dependencies.
**Precision:** 90% — All imports found, but only one direction of the dependency graph.

## Arrow Round (trace_dependencies)

**Method:** Single `trace_dependencies` call with `file="src/arrow/search.py"`.

**Tools used:** 1
**Time:** 6170 ms (1774009936352 → 1774009942522)
**Estimated tokens returned:** ~350

**Answer found:**

Direct imports (same as traditional):
- `__future__`, `logging`, `os`, `re`, `dataclasses`, `typing`, `tiktoken`
- `.chunker` (decompress_content), `.config` (get_config), `.storage` (ChunkRecord, Storage), `.vector_store` (VectorStore)

Imported by (13 files):
- `benchmarks/bench.py`, `benchmarks/bench_comparison.py`, `demo_comparison.py`
- `src/arrow/cli.py`, `src/arrow/server.py`, `src/arrow/vector_store.py`
- 7 test files

Transitive importers (depth 2): 26 additional files that transitively depend on `search.py` via `server.py`, `vector_store.py`, and `cli.py`.

**Quality:** 5/5 — Complete bidirectional dependency graph with transitive importers at depth 2. Shows the full impact surface.
**Precision:** 98% — All direct imports, all reverse dependencies, plus transitive graph.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Tool calls | 1 | 1 |
| Wall time (ms) | 4532 | 6170 |
| Tokens consumed | ~240 | ~350 |
| Quality (1-5) | 4 | 5 |
| Precision (%) | 90 | 98 |
| Reverse deps | No | Yes (13 files) |
| Transitive deps | No | Yes (26 files, depth 2) |

## Verdict

Arrow is slightly slower on wall time but provides substantially richer output. The traditional approach only answers "what does search.py import" while Arrow answers both directions: what it imports AND what imports it, plus the transitive importer graph. For a dependency question, the reverse/transitive view is arguably more valuable than just the forward imports. Arrow wins on completeness; traditional wins on speed for a simpler answer.
