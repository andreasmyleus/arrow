# Query 18: Find all tests that exercise the search pipeline

**Category:** get_tests_for — Tests
**Arrow tool under test:** `get_tests_for`
**Query:** "Find all tests that exercise the search pipeline"

---

## Ground Truth

Test files that exercise the search pipeline (search.py functions, search server endpoints, search helpers):

| File | What it tests | Key test count |
|------|--------------|----------------|
| `tests/test_core.py` | HybridSearcher, reciprocal_rank_fusion, _extract_query_concepts, _filename_match_boost, FTS search, symbol search | ~12 tests |
| `tests/test_precision.py` | filter_by_relevance, TestSearchPrecision (integration), estimate_budget | ~14 tests |
| `tests/test_server.py` | search_code, search_structure server endpoints, cross-project search, CWD scoping | ~10 tests |
| `tests/test_search_regex.py` | search_regex, _search_regex_on_disk, regex helpers | ~17 tests |
| `tests/test_doc_search.py` | _is_doc_query, _is_doc_path search helpers | ~15 tests |
| `tests/test_edge_cases.py` | TestSearchEdgeCases: empty index, special chars, tiny budget | ~4 tests |
| `tests/test_noncode_chunking.py` | Index-and-search integration for TOML, YAML, Dockerfile, Markdown | ~4 tests |
| `tests/test_vector_store.py` | Vector store add_and_search, empty_search | 2 tests |
| `tests/test_frecency.py` | frecency_boost_in_search | 1 test |
| `tests/test_tool_chain.py` | Integration chain using search_code | indirect |

**Total:** ~10 files, ~80+ individual test functions

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| **Start** | 1774012351008 |
| **End** | 1774012392732 |
| **Duration** | 41.7s |
| **Tool calls** | 12 (3 Glob, 3 Grep, 5 Read, 1 Grep follow-up) |
| **Estimated tokens** | ~12,000 |
| **Quality** | 5/5 |
| **Precision** | 95% |
| **Recall** | 95% |

**Approach:** Globbed for `*search*` test files, grepped for imports from `arrow.search` and search-related function references, then read key files to confirm test content. Found all 10 relevant test files and identified the specific test classes/functions in each.

**Strengths:** Comprehensive coverage. Found indirect references (test_tool_chain, test_noncode_chunking searchability tests, test_frecency) that naming conventions alone would miss.

**Weaknesses:** Required multiple rounds of searching and reading. High token cost from reading file contents to confirm relevance.

---

## Round 2 — Arrow (`get_tests_for`)

| Metric | Value |
|--------|-------|
| **Start** | 1774012395802 |
| **End** | 1774012405812 |
| **Duration** | 10.0s |
| **Tool calls** | 1 |
| **Estimated tokens** | ~4,500 |
| **Quality** | 3/5 |
| **Precision** | 100% |
| **Recall** | 50% |

**Results:** 20 test functions shown (out of 46 found internally), from 4 files:
- `tests/test_core.py` — FTS, symbol search, HybridSearcher, TestSearch class
- `tests/test_server.py` — search_code, search_structure server endpoints
- `tests/test_edge_cases.py` — empty index, special characters
- `tests/test_precision.py` — TestSearchPrecision, filter_by_relevance tail filtering

**Missing files (6):**
- `tests/test_search_regex.py` — entire regex search test suite
- `tests/test_doc_search.py` — doc-aware search helpers
- `tests/test_noncode_chunking.py` — index+search integration for config files
- `tests/test_vector_store.py` — vector search layer
- `tests/test_frecency.py` — frecency boost in search
- `tests/test_tool_chain.py` — integration test using search

**Strengths:** Fast, single call, returned actual test source code for immediate inspection. All returned results were genuinely relevant (100% precision).

**Weaknesses:** Only covered 4/10 relevant files (~50% recall). The tool searched for "search" as a function name, which found tests for `search()`, `search_code()`, `search_structure()`, `search_symbols()`, and `search_fts()` — but missed tests for related pipeline components like `search_regex`, `_is_doc_query`, vector store search, and frecency boost. The "showing 20/46" cap also hid results that might have included some of the missing files.

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| **Duration** | 41.7s | 10.0s | Arrow (4x faster) |
| **Tool calls** | 12 | 1 | Arrow |
| **Tokens** | ~12,000 | ~4,500 | Arrow (2.7x less) |
| **Quality** | 5/5 | 3/5 | Traditional |
| **Precision** | 95% | 100% | Arrow |
| **Recall** | 95% | 50% | Traditional |
| **Includes source** | Partial (read selectively) | Yes (all 20 results) | Arrow |

**Winner: Traditional** for this broad query.

**Analysis:** `get_tests_for` is designed for finding tests for a specific function, not for a broad concept like "the search pipeline." When called with `function="search"`, it correctly found tests that reference or test functions literally named `search*`, but the search pipeline spans many functions (`search_regex`, `_is_doc_query`, `filter_by_relevance`, vector store search, frecency boost) that don't share the "search" name prefix.

A better Arrow strategy would be multiple `get_tests_for` calls for each pipeline component, or using `search_code("search pipeline test")` + `get_context` to cast a wider net. The tool performed well for its designed purpose (single-function test lookup) but the query required broader concept-level search.
