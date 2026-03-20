# Query 18: Find all tests that exercise the search pipeline

**Category:** Test discovery
**Arrow tool:** `get_tests_for`
**Date:** 2026-03-20

## Query

"Find all tests that exercise the search pipeline"

## Traditional Round (Glob + Grep + Read)

**Method:** Glob for test files with "search" in the name, Grep for `def test.*search` across all test files, Grep for imports from `arrow.search` and `arrow.server`, then Read key test files to confirm content.

**Tools used:** 7 (2 Glob, 3 Grep, 2 Read)
**Time:** 20353 ms (1774009931984 → 1774009952337)
**Estimated tokens:** ~2200 (Grep outputs ~400 lines x 4 + Read ~75 lines x 4)

**Answer found:**

Dedicated search test files:
- `tests/test_search_regex.py` — regex search tool tests (15+ test functions)
- `tests/test_doc_search.py` — documentation-aware search ranking tests
- `tests/test_precision.py` — search precision filtering (filter_by_relevance, SearchPrecision, RRF edge cases)

Tests in other files exercising search:
- `tests/test_core.py` — `test_insert_and_search_fts`, `test_search_fts_project_scoped`, `test_search_symbols`, `test_search_symbols_exact_match_priority`, `test_search_symbols_kind_filter`, `test_hybrid_search`, `test_hybrid_search_project_scoped`, `test_get_context`, `test_get_context_has_project_field`, `test_filename_boost_in_ranking`
- `tests/test_server.py` — `test_search_code`, `test_search_code_no_results`, `test_search_structure` (5 variants), `test_search_across_projects`, `test_search_scoped_to_project`, `test_search_code_scoped_to_cwd_project`
- `tests/test_edge_cases.py` — `test_search_empty_index`, `test_search_special_characters`
- `tests/test_vector_store.py` — `test_add_and_search`, `test_empty_search`
- `tests/test_noncode_chunking.py` — 4 "is_indexed_and_searchable" tests
- `tests/test_frecency.py` — `test_frecency_boost_in_search`
- `tests/test_tool_chain.py` — full agent session exercises search_code, search_structure, get_context

Total: ~28 distinct test functions across 8 files.

**Quality:** 5/5 — Comprehensive enumeration of all search-related tests with file locations and function names.
**Precision:** 95% — Thorough multi-strategy search (name patterns, imports, content) caught tests across many files.

## Arrow Round (get_tests_for)

**Method:** Single `get_tests_for(function="search", project="andreasmyleus/arrow")` call.

**Tools used:** 1
**Time:** 11459 ms (1774009954703 → 1774009966162)
**Estimated tokens returned:** ~8000 (74 test matches with full source code)

**Answer found:**

74 matches returned with full source code, spanning:
- `tests/test_core.py` — `test_search_fts_project_scoped`, `test_search_symbols`, `test_search_symbols_exact_match_priority`, `test_search_symbols_kind_filter`, `test_hybrid_search`, `test_hybrid_search_project_scoped`, `test_filename_boost_in_ranking`
- `tests/test_frecency.py` — `test_frecency_boost_in_search`
- `tests/test_server.py` — `test_search_code`, `test_search_code_no_results`, `test_search_structure` (5 variants), `test_search_across_projects`, `test_search_scoped_to_project`, `test_search_code_scoped_to_cwd_project`
- `tests/test_edge_cases.py` — `test_search_empty_index`, `test_search_special_characters`
- `tests/test_vector_store.py` — `test_add_and_search`, `test_empty_search`, `test_save_and_load`, `test_remove`, `test_high_dimensionality`
- `tests/test_tool_chain.py` — `test_full_agent_session` (807 lines of code)
- `tests/test_search_regex.py` — `test_searches_non_code_files`
- `benchmarks/arrow_vs_traditional_test_spec.md` — spec document (not a test)

Also included full source code for each test function.

**Quality:** 4/5 — Found many relevant tests and included source code, but the broad "search" function name caused some noise: vector_store tests for save/load/remove aren't really "search pipeline" tests, the full 807-line tool_chain test is excessive context, and a benchmark spec doc was included. Some tests from test_precision.py and test_doc_search.py were missing since they don't match the "search" function name pattern directly.
**Precision:** 75% — Good recall but lower precision due to the broad match. The 74 results include noise (vector store internals, unrelated test_tool_chain megafunction, benchmark docs) and miss some relevant tests (test_precision.py's `TestFilterByRelevance` and `TestSearchPrecision` classes, test_doc_search.py tests).

## Comparison

| Metric | Traditional | Arrow |
|--------|-----------|-------|
| Tool calls | 7 | 1 |
| Wall time | 20.4 s | 11.5 s |
| Tokens consumed | ~2,200 | ~8,000 |
| Quality | 5/5 | 4/5 |
| Precision | 95% | 75% |

## Analysis

**Speed:** Arrow was 1.8x faster (11.5s vs 20.4s), using a single tool call instead of 7.

**Token efficiency:** Arrow returned ~3.6x more tokens (~8,000 vs ~2,200). The bulk came from full source code of all 74 matches, including the 807-line `test_full_agent_session` function. For this query, traditional was more token-efficient since it returned just function names and locations.

**Quality:** Traditional wins here. The multi-strategy approach (name pattern + import tracing + content grep) gave a curated, high-precision list. Arrow's `get_tests_for` with the broad term "search" cast too wide a net — it matched anything containing "search" in the function name or body, pulling in vector store internals and benchmark docs. It also missed `test_precision.py` and `test_doc_search.py` tests that exercise search internals (filter_by_relevance, _is_doc_query) because those don't match the "search" function name pattern.

**Verdict:** Traditional approach wins for this query. The `get_tests_for` tool is designed for specific function names (e.g., "get_user", "cache_get") where it excels. For broad concepts like "the search pipeline," the traditional multi-strategy approach produces a more precise and complete answer with fewer tokens.
