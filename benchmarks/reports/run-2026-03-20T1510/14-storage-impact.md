# Query 14: Storage Class Constructor Impact

**Query:** "If I change the Storage class constructor, what breaks?"
**Category:** what_breaks_if_i_change — Impact
**Arrow tool under test:** `what_breaks_if_i_change`
**Timestamp:** 2026-03-20T15:10

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774012330769
**End:** 1774012350477
**Duration:** 19,708 ms

### Method
1. Grep for `from.*storage.*import.*Storage` to find all import sites.
2. Grep for `Storage(` to find all direct instantiation sites.
3. Grep for `_get_storage` and `storage` parameter usage to find indirect dependents.
4. Read `storage.py` to confirm constructor signature: `__init__(self, db_path: str | Path)`.
5. Grep test directory for Storage references.

### Findings

**Constructor signature:** `Storage.__init__(self, db_path: str | Path)` at line 243 of `src/arrow/storage.py`.

**Direct instantiation sites (10):**
- `src/arrow/server.py` — 2 sites (`_storage = Storage(db_path)` and fallback `Storage(...)`)
- `src/arrow/cli.py` — 1 site (`Storage(db)`)
- `tests/test_core.py`, `tests/test_edge_cases.py`, `tests/test_noncode_chunking.py`, `tests/test_precision.py` — 4 test files
- `benchmarks/bench.py`, `benchmarks/bench_comparison.py`, `demo_comparison.py` — 3 support files

**Direct imports (13 files):**
- Source: `server.py`, `indexer.py`, `search.py`, `cli.py`
- Tests: `test_core.py`, `test_edge_cases.py`, `test_noncode_chunking.py`, `test_precision.py`, `test_storage_methods.py`
- Other: `bench.py`, `bench_comparison.py`, `demo_comparison.py`, CI workflow

**Indirect dependents via `_get_storage()` (3 files, 18 call sites):**
- `tools_analysis.py` — 6 call sites
- `tools_data.py` — 11 call sites
- `tools_github.py` — 1 call site

**Limitations:** Manual grep found import sites and direct `Storage(` calls but missed several test files that import Storage indirectly (e.g., `test_export_import.py`, `test_frecency.py`, `test_conversation.py`, `test_analytics.py`, `test_stale_index.py`, `test_auto_warm.py`, `test_imports.py`, `test_dead_code.py`, `test_memory.py`). Also did not produce a risk assessment or enumerate individual test functions that would break.

### Metrics
| Metric | Value |
|--------|-------|
| Tool calls | 7 (3 Grep, 1 Read, 3 Grep) |
| Estimated tokens | ~5,500 |
| Quality | 3/5 |
| Precision | 60% |

---

## Round 2 — Arrow (`what_breaks_if_i_change`)

**Start:** 1774012358787
**End:** 1774012367361
**Duration:** 8,574 ms

### Method
Single call: `what_breaks_if_i_change(file="src/arrow/storage.py", function="Storage", project="andreasmyleus/arrow")`

### Findings

**Risk level:** HIGH

**Callers (34):**
- 2 source callers: `demo_comparison.py` (2 functions), `demo_part2.py` (1 function)
- 2 benchmark callers: `bench_indexing`, `bench_search` in `benchmarks/bench.py`
- 30 test callers across 13 test files, including individual test functions and classes

**Affected tests (30 named, 38 total including sub-references):**
- `tests/conftest.py` — `clean_server_state`
- `tests/test_core.py` — `db`, `test_ignores_binary`, `TestStorage`
- `tests/test_edge_cases.py` — `db`, `test_unicode_filename`, `TestStorageEdgeCases`
- `tests/test_storage_methods.py` — `TestStorageNewMethods`, `test_count_fts_hits`, `test_get_test_files`, `test_get_importers_of_file`, `test_resolve_symbol_across_repos`
- `tests/test_export_import.py` — `test_export_produces_json`, `test_import_creates_project`
- `tests/test_frecency.py` — `test_record_file_access`, `test_frecency_boost_in_search`, `test_frecency_decay`
- `tests/test_conversation.py` — `test_session_chunk_tracking`, `test_session_clear`
- `tests/test_server.py` — `test_detect_project_from_cwd_matches_root`, `test_resolve_project_id_explicit_name_still_works`
- `tests/test_analytics.py` — `test_record_and_retrieve`
- `tests/test_stale_index.py` — `test_detect_stale_specific_project`
- `tests/test_imports.py` — `test_python_imports_indexed`
- `tests/test_dead_code.py` — `test_dead_code_with_project`
- `tests/test_memory.py` — `test_project_scoped_memory`
- `tests/test_auto_warm.py` — `test_auto_warm_indexes_git_dir`
- `tests/test_precision.py` — `db`
- `tests/test_noncode_chunking.py` — `db`

**Dependent files (12):**
- Source: `server.py`, `cli.py`, `indexer.py`, `search.py`
- Tests: `test_core.py`, `test_server.py`, `test_edge_cases.py`, `test_precision.py`, `test_noncode_chunking.py`
- Other: `demo_comparison.py`, `bench.py`, `bench_comparison.py`

**Limitation:** Did not list `tools_analysis.py`, `tools_data.py`, `tools_github.py` as dependent files, even though they are indirect dependents via `_get_storage()`. The dependent_files list appears to track only files that directly import Storage.

### Metrics
| Metric | Value |
|--------|-------|
| Tool calls | 1 |
| Estimated tokens | ~2,800 |
| Quality | 4/5 |
| Precision | 85% |

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Duration | 19,708 ms | 8,574 ms | Arrow (2.3x faster) |
| Tool calls | 7 | 1 | Arrow (7x fewer) |
| Tokens (est.) | ~5,500 | ~2,800 | Arrow (2x fewer) |
| Callers found | 10 direct instantiation sites | 34 individual callers | Arrow |
| Tests found | 5 test files (no function-level detail) | 30 named test functions across 13 files | Arrow |
| Dependent files | 8 source + indirect files | 12 listed | Arrow |
| Risk assessment | None | HIGH | Arrow |
| Quality | 3/5 | 4/5 | Arrow |
| Precision | 60% | 85% | Arrow |

### Key Observations

1. **Breadth of test discovery:** Arrow found 30 individual test functions across 13 test files, while the traditional approach only found 5 test files that directly import Storage. Arrow discovers tests in files like `test_frecency.py`, `test_conversation.py`, `test_analytics.py`, `test_stale_index.py`, `test_auto_warm.py`, etc. that the traditional grep missed entirely.

2. **Granularity:** Arrow provides function-level detail (which specific test functions and callers), while the traditional approach stays at the file level unless additional reads are done (which would increase tool calls and time).

3. **Missing indirect dependents:** Arrow's `dependent_files` list omits `tools_analysis.py`, `tools_data.py`, and `tools_github.py`, which depend on Storage indirectly via `_get_storage()`. These are genuinely affected if the constructor changes (since `_get_storage()` calls `Storage(db_path)`). The traditional approach found these via explicit `_get_storage` grep.

4. **Risk assessment:** Arrow provided a "HIGH" risk rating automatically. The traditional approach provides no such assessment without manual analysis.

5. **Some noise:** Arrow included 3 entries from `benchmarks/arrow_vs_traditional_test_spec.md` in affected_tests, which are documentation references, not actual tests. This slightly inflates the test count.
