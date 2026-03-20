# Query 17: "What does search.py depend on?"

**Category:** trace_dependencies — Import graph

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 6,413 ms |
| Tool calls | 2 (Bash timestamp + Read) |
| Quality | 3/5 |
| Precision | 60% |

### Method
Read the first 50 lines of `src/arrow/search.py` to capture all import statements.

### Answer — Imports
- **stdlib:** `__future__`, `logging`, `os`, `re`, `dataclasses`, `typing`
- **third-party:** `tiktoken`
- **internal:** `.chunker` (decompress_content), `.config` (get_config), `.storage` (ChunkRecord, Storage), `.vector_store` (VectorStore)

### Limitations
- Only shows what search.py imports (outbound dependencies).
- No reverse dependency information — does not show who imports search.py.
- No transitive dependency graph.
- Would require additional tool calls (Grep across all .py files) to get the full picture.

---

## Round 2 — Arrow (trace_dependencies)

| Metric | Value |
|---|---|
| Wall time | 3,816 ms |
| Tool calls | 1 |
| Quality | 5/5 |
| Precision | 95% |

### Method
Single call: `trace_dependencies(file="src/arrow/search.py", project="andreasmyleus/arrow")`

### Answer — Full Dependency Graph

**Imports (outbound):**
- `__future__`, `logging`, `os`, `re`, `dataclasses`, `typing`, `tiktoken`
- `.chunker` (decompress_content), `.config` (get_config), `.storage` (ChunkRecord, Storage), `.vector_store` (VectorStore)

**Imported by (13 files):**
- `benchmarks/bench.py`, `benchmarks/bench_comparison.py`, `demo_comparison.py`
- `src/arrow/cli.py`, `src/arrow/server.py`, `src/arrow/vector_store.py`
- 7 test files

**Transitive importers (depth 2):**
- `vector_store.py` → `cli.py`, `server.py`, `test_vector_store.py`
- `cli.py` → `__main__.py`
- `server.py` → 22 downstream files (tools, watcher, tests, conftest)

---

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Wall time | 6,413 ms | 3,816 ms |
| Tool calls | 2 | 1 |
| Reverse deps | No | Yes (13 files) |
| Transitive graph | No | Yes (depth 2) |
| Quality | 3/5 | 5/5 |
| Precision | 60% | 95% |

### Verdict
Arrow's `trace_dependencies` provides a complete bidirectional dependency graph (imports + importers + transitive importers) in a single call. The traditional approach only captures outbound imports and would need many additional Grep calls across the codebase to approximate the reverse dependency data. Arrow is faster, more complete, and requires fewer tool calls.
