# Query 15: Blast radius of changing `chunk_file` in `chunker.py`

**Category:** `what_breaks_if_i_change` — Impact analysis
**Date:** 2026-03-20
**Query:** "What's the blast radius of changing chunk_file in chunker.py?"

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Start | 1774007854155 |
| End | 1774007865416 |
| Duration | 11,261 ms |
| Tool calls | 7 (3 Grep + 1 Read + 1 Grep + 2 Bash) |
| Quality | 4/5 |
| Precision | 85% |

### Findings

**Direct callers (source):**
- `src/arrow/indexer.py` — `index_codebase`, `index_remote_files`, `index_git_commit` (lines 171, 299, 453)
- `src/arrow/tools_analysis.py` — `get_diff_context` (line 239)

**Internal callers (within chunker.py):**
- `chunk_file_treesitter`, `_chunk_file_regex`, `chunk_file_fallback` are called *by* `chunk_file`, not callers of it

**Test files:**
- `tests/test_edge_cases.py` — 11 direct calls across 9 test functions
- `tests/test_noncode_chunking.py` — 5 direct calls (TOML, YAML, JSON, Markdown, Dockerfile routing)
- `tests/test_core.py` — 2 direct calls (`test_chunk_python_file`, `test_chunk_fallback`)

**Indirect dependents (via indexer.py):**
- `src/arrow/server.py` — calls `indexer.index_codebase`
- `src/arrow/tools_github.py` — calls `indexer.index_remote_files`, `index_codebase`, `index_git_commit`, `index_pr`
- `src/arrow/cli.py` — calls `indexer.index_codebase`, `index_git_commit`, `index_pr`

**Limitations:** Required manual tracing of second-order dependencies. Did not discover `server.py` or `search.py` as direct importers of `chunk_file` (would need additional grep passes). Missed `search.py` entirely.

---

## Round 2 — Arrow (`what_breaks_if_i_change`)

| Metric | Value |
|---|---|
| Start | 1774007868014 |
| End | 1774007875245 |
| Duration | 7,231 ms |
| Tool calls | 1 |
| Quality | 5/5 |
| Precision | 90% |

### Findings

Single tool call returned structured JSON impact report:

- **Risk level:** HIGH
- **Total callers:** 28 (across source and test code)
- **Total affected tests:** 21
- **Total dependent files:** 8

**Direct callers in source:**
- `src/arrow/indexer.py` — `index_codebase`, `index_remote_files`, `index_git_commit`
- `src/arrow/tools_analysis.py` — `get_diff_context`
- `src/arrow/server.py` — `_search_regex_in_chunks`, `search_structure`
- `src/arrow/search.py` — `search`

**Dependent files:**
- `src/arrow/server.py`, `src/arrow/indexer.py`, `src/arrow/search.py`, `src/arrow/tools_analysis.py`, `src/arrow/tools_data.py`
- `tests/test_core.py`, `tests/test_edge_cases.py`, `tests/test_noncode_chunking.py`

**Affected tests:** 21 test functions across 3 test files plus benchmark spec references.

**Notes:** Arrow found callers in `server.py` and `search.py` that the traditional approach missed in the same time budget. It also included some false positives (listing `chunk_file_treesitter`, `_chunk_file_regex`, `chunk_file_fallback` as callers of `chunk_file` when they are actually callees). The `tools_data.py` dependent is also questionable — it likely depends on chunker indirectly. Precision docked slightly for these.

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|---|---|---|---|
| Duration | 11,261 ms | 7,231 ms | Arrow (1.6x faster) |
| Tool calls | 7 | 1 | Arrow (7x fewer) |
| Callers found (source) | 4 functions in 2 files | 7 functions in 4 files | Arrow |
| Tests identified | 18 test calls in 3 files | 21 tests in 3 files | Arrow |
| Dependent files | 5 (with manual tracing) | 8 (automatic) | Arrow |
| Risk assessment | Manual | Automatic (HIGH) | Arrow |
| Precision | 85% | 90% | Arrow |
| Quality | 4/5 | 5/5 | Arrow |

### Summary

Arrow's `what_breaks_if_i_change` provides a comprehensive, structured impact report in a single call. It found callers in `server.py` (`_search_regex_in_chunks`, `search_structure`) and `search.py` (`search`) that the traditional grep-based approach missed within its time budget. The automatic risk assessment (HIGH) and structured output (callers, tests, dependents) give immediately actionable information. The traditional approach required 7 tool calls and manual reasoning to trace second-order dependencies, yet still missed direct callers. Arrow had minor precision issues (listing internal callees as callers), but overall delivered a more complete and faster result.

**Winner: Arrow** — faster, more complete, structured output with risk assessment.
