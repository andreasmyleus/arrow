# Query 14: If I change the `Storage` class constructor, what breaks?

**Category:** Impact
**Arrow tool(s):** `what_breaks_if_i_change`
**Timestamp:** 2026-03-20T14:48

---

## Round 1 — Traditional (Glob + Grep + Read)

**Time:** 17,734 ms (1774010974909 -> 1774010992643)
**Tool calls:** 7 (5 Grep, 1 Read, 1 Grep for test files)
**Lines read:** ~30 (Storage constructor)
**Estimated tokens:** ~3,200 (output from grep results across multiple calls)

### Approach
1. Grep for `class Storage` to locate the definition.
2. Grep for `from.*storage.*import|import.*storage` across the entire repo.
3. Grep for `Storage(` to find all direct instantiation sites.
4. Read the constructor (lines 240-269) to understand the signature: `__init__(self, db_path: str | Path)`.
5. Grep for `storage: Storage`, `_storage`, and `_get_storage` to find indirect users.
6. Grep for `Storage|_get_storage|storage` in `tests/` to find affected test files.

### Findings
**Constructor:** `Storage.__init__(self, db_path: str | Path)` at storage.py:243

**Direct importers (source):**
- `src/arrow/server.py` — imports `Storage`, creates singleton via `_get_storage()`
- `src/arrow/indexer.py` — imports `Storage`, accepts as constructor arg
- `src/arrow/search.py` — imports `ChunkRecord, Storage`, accepts in `HybridSearcher.__init__`
- `src/arrow/cli.py` — imports `Storage` (lazy), creates in `_get_components()`

**Indirect users via `_get_storage()`:**
- `src/arrow/tools_analysis.py` — 6 call sites
- `src/arrow/tools_github.py` — 1 call site
- `src/arrow/tools_data.py` — 11 call sites

**Direct instantiation sites (10):**
- `server.py:68`, `cli.py:34`, `bench.py:43`, `bench_comparison.py:233`, `demo_comparison.py:186`, `ci.yml:48`
- Test fixtures: `test_core.py:32`, `test_edge_cases.py:19`, `test_noncode_chunking.py:26`, `test_precision.py:21`

**Test files referencing Storage:** 16 files in `tests/`

**Limitations:** Could not enumerate specific test function names without reading each file. Missed `demo_part2.py`. No risk assessment. No caller-level granularity for indirect users (tools_analysis, tools_data, etc.).

**Quality:** 3/5 — Found import sites and instantiation sites but lacked function-level caller detail and risk assessment.
**Precision:** 75% — Found most direct dependents but missed some files (demo_part2.py) and could not enumerate individual affected test functions.

---

## Round 2 — Arrow (`what_breaks_if_i_change`)

**Time:** 13,254 ms (1774011000656 -> 1774011013910)
**Tool calls:** 1
**Tokens received:** ~3,800 (structured JSON response)

### Findings
**Risk level:** HIGH

**Callers (34 total):**
- 2 in `demo_comparison.py` (run_arrow, main)
- 1 in `demo_part2.py` (p)
- 1 in `tests/conftest.py` (clean_server_state)
- 3 in `tests/test_core.py` (db fixture, test_ignores_binary, TestStorage class)
- 2 in `tests/test_export_import.py`
- 1 in `tests/test_imports.py`
- 5 in `tests/test_storage_methods.py`
- 1 in `tests/test_analytics.py`
- 1 in `tests/test_stale_index.py`
- 3 in `tests/test_frecency.py`
- 2 in `tests/test_conversation.py`
- 2 in `tests/test_server.py`
- 1 in `tests/test_dead_code.py`
- 1 in `tests/test_memory.py`
- 3 in `tests/test_edge_cases.py`
- 1 in `tests/test_auto_warm.py`
- 1 in `tests/test_noncode_chunking.py`
- 1 in `tests/test_precision.py`
- 2 in `benchmarks/bench.py`

**Affected tests:** 27 test functions/fixtures across 13 test files (plus 3 benchmark spec references)

**Dependent files (12):** server.py, cli.py, indexer.py, search.py, test_core.py, test_server.py, test_edge_cases.py, test_precision.py, test_noncode_chunking.py, bench.py, bench_comparison.py, demo_comparison.py

**Limitation:** Did not list `tools_analysis.py`, `tools_github.py`, or `tools_data.py` as dependent files, even though they indirectly depend on Storage via `_get_storage()`. These are indirect dependents (they call `_get_storage()` from server.py, not `Storage()` directly), so the omission is debatable.

**Quality:** 4/5 — Comprehensive caller-level detail with function names, risk assessment, and test enumeration. Missing indirect dependents via `_get_storage()`.
**Precision:** 85% — Excellent direct caller coverage with function-level granularity. Missed indirect tool files that depend on Storage through `_get_storage()`.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 17,734 ms | 13,254 ms |
| Tool calls | 7 | 1 |
| Tokens (est.) | ~3,200 | ~3,800 |
| Quality (1-5) | 3 | 4 |
| Precision | 75% | 85% |
| Risk assessment | No | Yes (HIGH) |
| Caller granularity | File-level | Function-level |
| Test enumeration | File-level (16 files) | Function-level (27 tests) |

### Key Observations

1. **Function-level granularity:** Arrow identified 34 individual callers with function/class names, while traditional grep only found ~10 instantiation sites and had to stop at file-level for indirect usage. This is the most valuable difference for impact analysis.

2. **Test enumeration:** Arrow listed 27 specific test functions across 13 files, giving a clear "what to re-run" list. Traditional grep found 16 test files but could not name individual tests without reading each file.

3. **Risk assessment:** Arrow provided a "HIGH" risk rating automatically. Traditional approach has no way to assess risk without manual reasoning.

4. **Blind spot:** Arrow's dependent_files list (12 files) missed `tools_analysis.py`, `tools_github.py`, and `tools_data.py` which depend on Storage indirectly through `_get_storage()`. Traditional grep actually caught these via the `_get_storage` pattern search. This is a meaningful gap for a "what breaks" tool.

5. **Speed:** Arrow was 25% faster (13.3s vs 17.7s) with 1 tool call vs 7, reducing cognitive overhead significantly.

**Winner:** Arrow -- the function-level caller detail and risk assessment provide substantially more actionable information for planning a constructor change, despite the indirect-dependency blind spot.
