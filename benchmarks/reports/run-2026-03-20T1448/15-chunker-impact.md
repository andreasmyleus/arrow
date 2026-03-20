# Query 15: Blast radius of changing `chunk_file` in chunker.py

**Category:** Impact
**Arrow tool:** `what_breaks_if_i_change`
**Date:** 2026-03-20

---

## Ground Truth (established via manual tracing)

`chunk_file` in `src/arrow/chunker.py` (line 1114) is the main entry point for file chunking. It dispatches to `chunk_file_treesitter`, `_chunk_file_regex`, section chunkers, or `chunk_file_fallback`.

### Direct callers (production code)
| File | Function | Lines |
|------|----------|-------|
| `src/arrow/indexer.py` | `index_codebase` | 171 |
| `src/arrow/indexer.py` | `index_remote_files` | 299 |
| `src/arrow/indexer.py` | `index_git_commit` | 453 |
| `src/arrow/tools_analysis.py` | `get_diff_context` | 237, 271 |

### Indirect callers (import but grep did not surface direct call)
| File | Function | Notes |
|------|----------|-------|
| `src/arrow/server.py` | `_search_regex_in_chunks` | Uses chunk_file for re-chunking |
| `src/arrow/server.py` | `search_structure` | Uses chunk_file for re-chunking |
| `src/arrow/search.py` | `search` | Potentially via import chain |

### Tests that directly call `chunk_file`
- `tests/test_core.py` (2 tests: `test_chunk_python_file`, `test_chunk_fallback`)
- `tests/test_edge_cases.py` (9 tests covering empty, single-line, syntax error, long function, nested, decorators, TS, Rust, Go, unknown extension)
- `tests/test_noncode_chunking.py` (5 tests: TOML, YAML, JSON, Markdown, Dockerfile routing)

### Dependent files (import `chunk_file`)
- `src/arrow/indexer.py`
- `src/arrow/tools_analysis.py`
- `src/arrow/server.py`

**Total: 4-7 production callers, 16 tests, 3-5 dependent files. Risk: HIGH.**

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 28,635 ms |
| Tool calls | 8 (Grep x4, Read x4) |
| Tokens consumed (est.) | ~620 |
| Quality | 3/5 |
| Precision | 85% |

### Approach
1. Grep for `def chunk_file` to locate the function definition (line 1114).
2. Read the function body (30 lines) to understand its dispatch logic.
3. Grep for `chunk_file` across `src/arrow/` and `tests/` to find all references.
4. Read surrounding context in indexer.py (3 call sites) and tools_analysis.py (2 call sites) to identify which functions contain the calls.
5. Grep for function definitions in indexer.py and tools_analysis.py to map call sites to function names.
6. Grep server.py to find upstream callers of the indexer functions.

### Findings
- Found 4 production callers (indexer.py x3, tools_analysis.py x1) with exact line numbers.
- Found 16 test call sites across 3 test files.
- Identified 3 dependent source files.
- **Missed:** `server.py` direct callers (`_search_regex_in_chunks`, `search_structure`) and `search.py` caller -- would have required additional grep passes checking imports from chunker in those files.
- **No risk assessment** -- requires manual judgment.

---

## Round 2 — Arrow (`what_breaks_if_i_change`)

| Metric | Value |
|--------|-------|
| Wall time | 12,717 ms |
| Tool calls | 1 |
| Tokens consumed (est.) | ~2,800 (large JSON response) |
| Chunks returned | 0 (structured report, not code chunks) |
| Quality | 4/5 |
| Precision | 75% |

### Findings
- Returned 28 callers, 21 affected tests, 8 dependent files.
- Correctly identified all production callers including ones traditional missed: `server.py` (`_search_regex_in_chunks`, `search_structure`), `search.py` (`search`).
- Correctly identified all 3 test files and most individual test names.
- Provided automatic risk assessment: **high**.
- Listed `tools_data.py` as a dependent file (not found by traditional).

### Issues
- **False positive callers:** Listed `chunk_file_treesitter`, `_chunk_file_regex`, and `chunk_file_fallback` as "callers" of `chunk_file`. These are actually **callees** (called BY `chunk_file`), not callers. This is a direction-of-call error.
- **False positive tests:** Some entries in `affected_tests` are not test functions but code chunks within test files (e.g., `MyClass`, `handler`, `outer_method` from test_edge_cases.py are test fixture code, not test names). Also included benchmark spec markdown sections as "tests".
- **Token-heavy response:** The JSON output was ~2,800 tokens -- more than traditional's ~620 tokens, though it contained more information.

---

## Comparison

| Dimension | Traditional | Arrow | Winner |
|-----------|-------------|-------|--------|
| Wall time | 28,635 ms | 12,717 ms | Arrow (2.3x faster) |
| Tool calls | 8 | 1 | Arrow |
| Tokens consumed | ~620 | ~2,800 | Traditional (4.5x less) |
| Production callers found | 4/7 | 7/7 (+ 3 false) | Arrow (broader but noisier) |
| Tests found | 16/16 | 16/16 (+ 5 false) | Tie (Arrow has noise) |
| Dependent files | 3 | 8 (incl. tests) | Arrow (more complete) |
| Risk assessment | None | High (auto) | Arrow |
| Precision | 85% | 75% | Traditional |
| Quality | 3/5 | 4/5 | Arrow |

## Verdict

**Arrow wins on speed and completeness** -- it found callers in `server.py` and `search.py` that the traditional approach missed without additional grep passes. The automatic risk assessment is valuable. However, Arrow's precision suffers from two issues: (1) it confuses callees with callers (listing functions that `chunk_file` calls as its "callers"), and (2) it includes non-test symbols from test files in the affected_tests list. The traditional approach was more precise but required more manual effort and still missed some callers.

For impact analysis, Arrow's broader coverage is more important than perfect precision -- missing a caller is riskier than having a few false positives. The callee-as-caller confusion should be fixed in the tool implementation.
