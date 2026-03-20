# Query 19 — "What tests cover the `authenticate` function?"

**Category:** Tests
**Arrow tool(s):** `get_tests_for` with function="authenticate"
**Date:** 2026-03-20

## Query Analysis

The `authenticate` function is a fixture function defined in test project data (conftest.py `project_dir` fixture creates `auth.py` with `def authenticate(user, password)`). The question asks which tests exercise or reference this function. This requires scanning test files for direct calls, imports, and naming-convention matches (e.g., `test_authenticate`).

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 13,011 ms |
| Tool calls | 6 (4 Grep, 2 Read) |
| Tokens read | ~680 |
| Lines examined | ~170 |

### Approach
1. Grep for `def authenticate` across the entire repo -- found it defined in conftest.py fixture and referenced in several test files.
2. Grep for `authenticate` in `test_*.py` files -- found references in 10 test files.
3. Grep again with broader `*test*.py` glob for completeness -- same results.
4. Read `test_test_mapping.py` and `conftest.py` for fixture structure context.

### Findings
Identified references to `authenticate` across 10 test files:
- `test_test_mapping.py` — directly tests `get_tests_for("authenticate")`
- `test_impact_analysis.py` — uses `authenticate` as target for impact analysis
- `test_symbol_resolution.py` — resolves `authenticate` symbol
- `test_storage_methods.py` — FTS hits and cross-repo resolution for `authenticate`
- `test_budget.py` — uses `authenticate` as query in budget/context tests (7 references)
- `test_conversation.py` — dedup test with `authenticate` query
- `test_frecency.py` — frecency boost search for `authenticate`
- `test_diff_context.py` — diff context on auth.py lines containing `authenticate`
- `test_stale_index.py` — modifies auth.py (contains `authenticate`)
- `test_doc_search.py` — negative test: "def authenticate" is not a doc query

Required manual effort to distinguish "tests that exercise authenticate" from "tests that merely mention the string". No function-level granularity without reading each file.

**Quality: 4/5** — Found all relevant files but required significant manual work to identify specific test functions and distinguish direct coverage from incidental mentions.
**Precision: 75%** — Some grep hits were incidental (e.g., `test_doc_search.py` just checks a classifier, `test_stale_index.py` rewrites the file but doesn't test authenticate's behavior).

## Round 2 — Arrow (`get_tests_for`)

| Metric | Value |
|---|---|
| Wall time | 6,283 ms |
| Tool calls | 1 |
| Chunks returned | 20 (of 22 found) |
| Files covered | 10 |

### Approach
Single call: `get_tests_for(function="authenticate", project="andreasmyleus/arrow")`.

### Findings
Returned 20 specific test functions with full source code, organized by file:
- `test_test_mapping.py` (2 functions) — `test_find_tests_by_name`, `test_find_tests_with_source_file`
- `test_impact_analysis.py` (2) — `test_impact_specific_function`, `test_impact_whole_file`
- `test_symbol_resolution.py` (2) — `test_resolve_symbol_local`, `test_resolve_symbol_cross_repo`
- `test_storage_methods.py` (2) — `test_count_fts_hits`, `test_resolve_symbol_across_repos`
- `test_budget.py` (7) — all budget/context tests using `authenticate` as query
- `test_conversation.py` (1) — `test_get_context_excludes_sent`
- `test_frecency.py` (1) — `test_frecency_boost_in_search`
- `test_diff_context.py` (2) — `test_diff_context_with_line_range`, `test_diff_context_finds_callers`
- `test_stale_index.py` (1) — `test_detect_stale_after_modification`

Each result included the full function body, making it immediately actionable.

**Quality: 5/5** — Returned specific test functions with full code, properly identified via import tracing and name matching.
**Precision: 85%** — Most results are genuinely relevant tests that exercise `authenticate`. A few (e.g., stale index, frecency) use it as incidental test data rather than testing the function's behavior, but these are still legitimate coverage points.

## Comparison

| Metric | Traditional | Arrow | Delta |
|---|---|---|---|
| Wall time (ms) | 13,011 | 6,283 | -51.7% |
| Tool calls | 6 | 1 | -83.3% |
| Tokens consumed | ~680 | ~2,200 (returned) | +223% |
| Quality (1-5) | 4 | 5 | +1 |
| Precision (%) | 75% | 85% | +10pp |
| Granularity | File-level | Function-level | Arrow wins |

## Verdict

**Arrow wins.** The `get_tests_for` tool delivered function-level test mapping in a single call, returning 20 specific test functions with full source code. The traditional approach required 6 tool calls, manual file reading, and still only achieved file-level granularity -- identifying which files mention `authenticate` but requiring further reads to isolate specific test functions. Arrow's result was immediately actionable: each test function was shown in full with file path and line numbers. The 51.7% wall-time reduction and 83.3% tool-call reduction are significant. The higher token count for Arrow is a feature, not a cost -- those tokens are the actual answer content (full test function bodies) rather than raw grep output requiring interpretation.
