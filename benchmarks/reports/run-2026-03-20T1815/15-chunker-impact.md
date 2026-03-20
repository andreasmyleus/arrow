# Query 15: Blast radius of changing `chunk_file` in `chunker.py`

**Category:** Impact analysis
**Query:** "What's the blast radius of changing chunk_file in chunker.py?"
**Arrow tool:** `what_breaks_if_i_change`

## Round 1 — Traditional (Glob + Grep + Read)

- **Start:** 1774009908162
- **End:** 1774009931792
- **Duration:** 23,630 ms
- **Tool calls:** 7 (3 Grep + 3 Read + 1 Grep)
- **Estimated tokens:** ~1,200 (300 lines read x 4 tokens/line)

### Findings

**Direct callers of `chunk_file`:**
- `src/arrow/indexer.py` — `index_codebase` (line 171), `index_remote_files` (line 299), `index_git_commit` (line 453)
- `src/arrow/tools_analysis.py` — `get_diff_context` (line 243)

**Internal callees (called *by* `chunk_file`, not callers):**
- `chunk_file_treesitter`, `_chunk_file_regex`, `chunk_file_fallback`

**Files that import from chunker.py:**
- `src/arrow/indexer.py` — imports `chunk_file`, `compress_content`, `detect_language`
- `src/arrow/tools_analysis.py` — imports `chunk_file`
- `src/arrow/search.py` — imports `decompress_content` (not `chunk_file`)
- `src/arrow/server.py` — imports `decompress_content` (not `chunk_file`)
- `src/arrow/tools_data.py` — imports `compress_content` (not `chunk_file`)

**Tests directly calling `chunk_file`:**
- `tests/test_core.py` — 2 tests
- `tests/test_edge_cases.py` — 9 tests
- `tests/test_noncode_chunking.py` — 5 tests

**Second-order callers (call indexer functions that use chunk_file):**
- `src/arrow/server.py` — `index_codebase` tool, auto-indexing
- `src/arrow/tools_github.py` — `index_github_repo`, `index_git_commit`, `index_pr`
- `src/arrow/cli.py` — CLI commands

**Quality:** 4/5 — Found all direct callers, tests, and second-order dependents. Correctly distinguished callees from callers. Did not find `server.py` or `search.py` as direct callers of `chunk_file` (they import other symbols from chunker, not `chunk_file` itself).
**Precision:** 90% — Accurate separation of direct vs indirect dependencies.

## Round 2 — Arrow (`what_breaks_if_i_change`)

- **Start:** 1774009934670
- **End:** 1774009942884
- **Duration:** 8,214 ms
- **Tool calls:** 1
- **Tokens returned:** ~2,500 (estimated from JSON response)

### Findings

Arrow returned a structured JSON report with:
- **28 callers** across source and test files
- **21 affected tests** across 4 test files + benchmark spec
- **8 dependent files**
- **Risk level:** high

**Key callers found:**
- `indexer.py`: `index_codebase`, `index_remote_files`, `index_git_commit`
- `tools_analysis.py`: `get_diff_context`
- `server.py`: `_search_regex_in_chunks`, `search_structure` (these are additional callers the traditional round did NOT find since they don't directly import `chunk_file`)
- `search.py`: `search` (also not found by traditional round)
- Internal: `chunk_file_treesitter`, `_chunk_file_regex`, `chunk_file_fallback` (listed as callers — these are actually callees, a false positive)

**Quality:** 4/5 — Comprehensive coverage, found callers in `server.py` and `search.py` that the traditional approach missed. However, includes false positives: `chunk_file_treesitter`, `_chunk_file_regex`, and `chunk_file_fallback` are listed as "callers" when they are actually called BY `chunk_file`. Also lists `search.py` and `server.py` functions that may reference `chunk_file` indirectly rather than calling it directly. Benchmark spec entries in affected_tests are noise.
**Precision:** 78% — Good recall but several false positives in both callers and tests lists.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Duration | 23,630 ms | 8,214 ms |
| Tool calls | 7 | 1 |
| Tokens used | ~1,200 | ~2,500 |
| Quality | 4/5 | 4/5 |
| Precision | 90% | 78% |
| Speedup | — | 2.9x |

**Arrow advantage:** 2.9x faster, single tool call, broader coverage (found callers in `server.py` and `search.py` that required additional grep passes in the traditional approach). Structured JSON output with risk assessment.

**Traditional advantage:** Higher precision. Correctly identified that `chunk_file_treesitter`/`_chunk_file_regex`/`chunk_file_fallback` are callees not callers. No false positives in test detection. Manual analysis allowed proper directional understanding of the call graph.

**Notes:** Arrow's recall is better — it surfaced `server.py::_search_regex_in_chunks` and `search.py::search` as potential callers that the traditional approach missed without extra grep rounds. However, the callee-as-caller false positive pattern (listing functions that `chunk_file` calls as if they call `chunk_file`) is a recurring issue that reduces precision. The `tools_data.py` dependent is also indirect — it imports `compress_content`, not `chunk_file`. For impact analysis, Arrow's broader net is arguably more useful despite lower precision, since missing a real dependency is worse than including a false one.
