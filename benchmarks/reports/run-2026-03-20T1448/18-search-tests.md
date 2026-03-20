# Query 18: Find all tests that exercise the search pipeline

**Category:** Tests
**Arrow tool(s):** `get_tests_for` with function="search"
**Timestamp:** 2026-03-20T14:48

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 19,073 ms |
| Tool calls | 6 (1 Glob + 3 Grep + 2 Read) |
| Lines read | ~310 |
| Est. tokens | ~1,240 |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Identified **10 test files** containing search-pipeline tests:

| File | Tests / relevance |
|---|---|
| `tests/test_core.py` | `test_insert_and_search_fts`, `test_search_fts_project_scoped`, `test_search_symbols`, `test_search_symbols_exact_match_priority`, `test_search_symbols_kind_filter`, `test_hybrid_search`, `test_hybrid_search_project_scoped` |
| `tests/test_server.py` | `test_search_code`, `test_search_code_no_results`, `test_search_structure` (5 variants), `test_search_across_projects`, `test_search_scoped_to_project`, `test_search_code_scoped_to_cwd_project` |
| `tests/test_search_regex.py` | 17 tests covering regex search, context lines, multiline, limits, error handling, on-disk fallback |
| `tests/test_doc_search.py` | `_is_doc_query` / `_is_doc_path` detection, doc-boost integration |
| `tests/test_precision.py` | `TestSearchPrecision` — relevance filtering, reciprocal rank fusion |
| `tests/test_edge_cases.py` | `test_search_empty_index`, `test_search_special_characters` |
| `tests/test_frecency.py` | `test_frecency_boost_in_search` |
| `tests/test_noncode_chunking.py` | `test_toml_is_indexed_and_searchable`, `test_dockerfile_is_indexed_and_searchable`, etc. |
| `tests/test_tool_chain.py` | Integration chain: `search_code` (5 calls), `search_regex` (5 calls) |
| `tests/test_vector_store.py` | `test_add_and_search`, `test_empty_search` |

Total: ~40+ individual test functions across 10 files.

### Method
Glob for files matching `test_*search*`, then Grep for `def test.*search` and `search_code|search_fts|hybrid_search|search_symbols|search_regex` across all test files, plus Read on key files to verify context.

---

## Round 2 — Arrow (`get_tests_for`)

| Metric | Value |
|---|---|
| Wall time | 10,937 ms |
| Tool calls | 1 |
| Chunks returned | 20 (of 46 total matches) |
| Est. tokens | ~1,800 (full source in response) |
| Quality | 4/5 |
| Precision | 90% |

### Findings

Returned 20 test functions with full source code, from 5 files:
- `tests/test_core.py` — 5 tests (FTS, symbols, symbol kind filter, exact match priority, TestSearch class)
- `tests/test_server.py` — 9 tests (search_code, search_structure variants, cross-project, scoped)
- `tests/test_edge_cases.py` — 3 items (class header, empty index, special chars)
- `tests/test_precision.py` — 2 items (class header, filters irrelevant tail)

### What was missed
The tool showed 20 of 46 matches. Files not shown in the top 20:
- `tests/test_search_regex.py` — 17 regex search tests (significant gap)
- `tests/test_doc_search.py` — doc-aware search ranking tests
- `tests/test_frecency.py` — frecency boost in search
- `tests/test_noncode_chunking.py` — searchability tests for non-code files
- `tests/test_tool_chain.py` — integration search calls
- `tests/test_vector_store.py` — vector search tests

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|---|---|---|---|
| Wall time | 19.1s | 10.9s | Arrow (1.7x faster) |
| Tool calls | 6 | 1 | Arrow |
| Completeness | ~40+ tests across 10 files | 20 of 46 matches, 5 files | Traditional |
| Source code shown | Partial (names + key reads) | Full source for 20 tests | Arrow |
| Precision | 95% | 90% | Traditional |
| Quality | 5/5 | 4/5 | Traditional |

## Verdict

**Arrow wins on speed and convenience** (single tool call, 1.7x faster, full source inline), but **Traditional wins on completeness**. The `get_tests_for` tool truncated results to 20 of 46 matches, omitting the entire `test_search_regex.py` file (17 tests) which is arguably the most important search-pipeline test file. For a broad "find all tests" query, the traditional approach was more thorough. Arrow would be better if the caller followed up with a second call or if the tool surfaced all 46 matches.

**Recommendation:** `get_tests_for` should either increase the default display limit or prioritize showing at least one test per file before filling slots from the same file. A `--all` flag or pagination would help for broad queries like this.
