# Query 17: What does search.py depend on?

**Category:** trace_dependencies — Dependencies
**Arrow tool under test:** `trace_dependencies`
**Timestamp:** 2026-03-20T15:10

## Ground Truth

`src/arrow/search.py` imports:
- **Stdlib:** `__future__.annotations`, `logging`, `os`, `re`, `dataclasses.dataclass`, `typing.Optional`
- **Third-party:** `tiktoken`
- **Internal:** `.chunker.decompress_content`, `.config.get_config`, `.storage.ChunkRecord`, `.storage.Storage`, `.vector_store.VectorStore`

Imported by (direct, within `src/arrow/`): `server.py`, `cli.py`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 8,554 ms |
| Tool calls | 3 (Read, Grep, timestamp x2 excluded) |
| Lines read | ~50 |
| Tokens (est.) | ~200 |
| Quality | 4/5 |
| Precision | 85% |

### Method
1. Read the first 50 lines of `search.py` to capture all import statements.
2. Grepped across `src/arrow/` for files that import from `search`.

### Findings
- Identified all 4 internal and 1 third-party dependency correctly.
- Found 2 direct importers within `src/arrow/` (server.py, cli.py).
- Did **not** trace transitive importers or test files that import search.py.
- Did **not** provide depth-2 transitive dependency graph.

### Limitations
- Manual approach only shows direct imports and direct importers — no transitive graph.
- Would need additional Grep calls to find test files and benchmark scripts that import search.py.
- No structured output; requires manual assembly of results.

---

## Round 2 — Arrow (`trace_dependencies`)

| Metric | Value |
|---|---|
| Wall time | 7,047 ms |
| Tool calls | 1 |
| Tokens (est.) | ~450 (structured JSON response) |
| Quality | 5/5 |
| Precision | 95% |

### Method
Single call: `trace_dependencies(file="src/arrow/search.py", project="andreasmyleus/arrow")`

### Findings
- Returned all imports (stdlib, third-party, internal) in a flat list.
- Returned 13 direct importers including test files, benchmarks, and demo scripts — far more complete than the traditional approach.
- Provided depth-2 transitive importers for `server.py` (26 files), `cli.py` (1 file), and `vector_store.py` (1 file).
- Structured JSON output ready for programmatic use.

### Minor Issues
- Import list is flat (modules and symbols mixed together, e.g., `.storage` and `ChunkRecord` appear as separate entries rather than grouped as `from .storage import ChunkRecord, Storage`). This is a presentation choice, not an error.

---

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Wall time | 8,554 ms | 7,047 ms |
| Tool calls | 3 | 1 |
| Completeness | Direct only | Direct + transitive (depth 2) |
| Importers found | 2 | 13 direct + 28 transitive |
| Structured output | No | Yes (JSON) |
| Quality | 4/5 | 5/5 |
| Precision | 85% | 95% |

## Verdict

**Arrow wins.** A single tool call returned a complete dependency graph — both what `search.py` depends on and the full tree of what depends on it, two levels deep. The traditional approach required 3 tool calls and still only captured direct relationships within `src/arrow/`, missing test files, benchmarks, and transitive importers entirely. Arrow's structured JSON output is also more useful for downstream analysis. The speed advantage is modest but Arrow delivers dramatically more information per call.
