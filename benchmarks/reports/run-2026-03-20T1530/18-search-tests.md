# Query 18: "Find all tests that exercise the search pipeline"

Category: get_tests_for — Test discovery
Arrow tool(s) under test: get_tests_for

## Round 1 — Traditional

**Timestamps:** start=1774007862493 end=1774007881744
**Wall time:** 19251ms
**Tool calls:** 4 (Glob x1, Grep x3)
**Tokens from content:** ~4500
**Answer quality:** 5
**Precision:** 95%

### Answer

Found 10 test files exercising the search pipeline, spanning multiple layers:

**Core search engine (unit tests):**
- `tests/test_core.py` — `TestSearch` class: `test_hybrid_search`, `test_hybrid_search_project_scoped`, `test_reciprocal_rank_fusion`, `test_rrf_k20_favors_top_ranks`, `test_filename_boost_in_ranking`; FTS tests: `test_insert_and_search_fts`, `test_search_fts_project_scoped`; symbol search: `test_search_symbols`, `test_search_symbols_exact_match_priority`, `test_search_symbols_kind_filter`

**Search precision & ranking:**
- `tests/test_precision.py` — `TestSearchPrecision` class: `test_get_context_relevance_floor`, `test_search_filters_irrelevant_tail`, `test_rrf_scores_realistic`, `test_rrf_with_two_lists_creates_cliff`

**Frecency boosting:**
- `tests/test_frecency.py` — `test_frecency_boost_in_search`, `test_frecency_decay`

**Doc search ranking:**
- `tests/test_doc_search.py` — `TestDocSearchRanking`: `test_doc_query_boosts_readme`

**Vector store (search substrate):**
- `tests/test_vector_store.py` — `test_add_and_search`, `test_empty_search`, `test_save_and_load`, `test_remove`, `test_high_dimensionality`

**Server-level search tools:**
- `tests/test_server.py` — `test_search_code`, `test_search_code_no_results`, `test_search_structure`, `test_search_structure_by_kind`, `test_search_structure_exact_match_priority`, `test_search_structure_prefix_fallback`, `test_search_structure_includes_source`, `test_search_across_projects`, `test_search_scoped_to_project`, `test_search_code_scoped_to_cwd_project`

**Regex search:**
- `tests/test_search_regex.py` — `TestSearchRegexOutput` (10 tests), `TestSearchRegexHelpers`

**Non-code searchability:**
- `tests/test_noncode_chunking.py` — `test_toml_is_indexed_and_searchable`, `test_dockerfile_is_indexed_and_searchable`, `test_yaml_is_indexed_and_searchable`, `test_markdown_is_indexed_and_searchable`

**Edge cases:**
- `tests/test_edge_cases.py` — `TestSearchEdgeCases`: `test_search_empty_index`, `test_search_special_characters`; FTS edge cases: `test_fts_special_characters`, `test_fts_empty_query`, `test_fts_very_long_query`

**Integration (full session):**
- `tests/test_tool_chain.py` — `test_full_agent_session` exercises `search_code` (steps 4-7, 73-74, 93, 95), `search_regex` (steps 31-35), `search_structure` (steps 8-10, 37, 96)

### Files read
- (none read directly — all data from Glob + Grep output)

## Round 2 — Arrow

**Timestamps:** start=1774007881744 end=1774007887859
**Wall time:** 6115ms
**Tool calls:** 1 (get_tests_for x1)
**Tokens from content:** ~8200 (Arrow-reported)
**Chunks returned:** 64 found
**Answer quality:** 4
**Precision:** 70%

### Answer

Arrow returned 64 test chunks matching "search". The results included full source code for each test function. Key files covered:

- `tests/test_core.py` — `test_search_fts_project_scoped`, `test_search_symbols`, `test_search_symbols_exact_match_priority`, `test_search_symbols_kind_filter`, `TestSearch` class, `test_hybrid_search`, `test_hybrid_search_project_scoped`, `test_filename_boost_in_ranking`
- `tests/test_frecency.py` — `test_frecency_boost_in_search`
- `tests/test_server.py` — `test_search_code`, `test_search_code_no_results`, `test_search_structure` (5 variants), `test_search_across_projects`, `test_search_scoped_to_project`, `test_search_code_scoped_to_cwd_project`
- `tests/test_edge_cases.py` — `TestSearchEdgeCases`, `test_search_empty_index`, `test_search_special_characters`
- `tests/test_vector_store.py` — `test_add_and_search`, `test_empty_search`, `test_save_and_load`, `test_remove`, `test_high_dimensionality`
- `tests/test_tool_chain.py` — `test_full_agent_session` (full 807-line function)
- `benchmarks/arrow_vs_traditional_test_spec.md` — non-test content (false positive)

**Missing from Arrow results:**
- `tests/test_precision.py` — RRF and relevance tests
- `tests/test_search_regex.py` — regex search tests
- `tests/test_doc_search.py` — doc search ranking tests
- `tests/test_noncode_chunking.py` — searchability integration tests
- `tests/test_budget.py` — relevance cutoff test
- `tests/test_storage_methods.py` — `test_count_fts_hits`

**False positives:**
- `benchmarks/arrow_vs_traditional_test_spec.md` — not a test file
- `test_full_agent_session` — massive 807-line function returned in full, most of which is unrelated to search

### Observations

**Winner: Traditional (Round 1)**

The traditional approach was more precise and complete. By combining Glob (find test files) with targeted Grep patterns (search-related function names, imports from search module), it identified all 10 test files and categorized them by search pipeline layer.

Arrow's `get_tests_for` found 64 chunks but had notable gaps:
1. **Missed entire test files** — `test_precision.py`, `test_search_regex.py`, `test_doc_search.py`, and `test_noncode_chunking.py` were absent despite being core search tests. This is because `get_tests_for` matches on function name "search" via import tracing and naming conventions, but these files may not have test functions named `test_search*` or may import search utilities under different names.
2. **Excessive output** — The 807-line `test_full_agent_session` was returned in full, consuming ~5000 tokens for a function where only ~10% is search-related.
3. **False positive** — The benchmark spec markdown file was returned as a "test" match.
4. **Token inefficiency** — Arrow used ~8200 tokens (with full source code) vs Traditional's ~4500 tokens (compact grep output), while finding fewer relevant files.

The traditional approach excelled here because "tests exercising the search pipeline" is a broad, cross-cutting query that benefits from multiple search strategies (file patterns + content patterns + import analysis) rather than a single function-name lookup. Arrow's `get_tests_for` is optimized for "find tests for function X" but struggles when the query is about an entire subsystem.

**Speed:** Arrow was 3.1x faster (6.1s vs 19.3s), but the speed advantage is offset by lower recall.
