# Query 19: What tests cover the authenticate function?

**Category:** get_tests_for — Tests
**Arrow tool under test:** `get_tests_for`

## Ground Truth

The `authenticate` function is a test fixture function defined in `tests/conftest.py` (creates `auth.py` with `def authenticate(user, password)`). Tests that cover or reference this function span multiple test files:

- `test_test_mapping.py` — `test_find_tests_by_name`, `test_find_tests_with_source_file` (directly test `get_tests_for("authenticate")`)
- `test_impact_analysis.py` — `test_impact_specific_function`, `test_impact_whole_file`, `test_impact_finds_tests` (use `authenticate` as the target function)
- `test_symbol_resolution.py` — `test_resolve_symbol_local`, `test_resolve_symbol_cross_repo` (resolve the `authenticate` symbol)
- `test_budget.py` — 6 tests use `get_context("authenticate")` as their query
- `test_conversation.py` — `test_get_context_excludes_sent` (queries `authenticate`)
- `test_frecency.py` — `test_frecency_boost_in_search` (searches `authenticate`)
- `test_storage_methods.py` — `test_count_fts_hits`, `test_resolve_symbol_across_repos` (use `authenticate` as input)
- `test_stale_index.py` — `test_detect_stale_after_modification` (modifies the `authenticate` function)
- `test_diff_context.py` — `test_diff_context_with_line_range`, `test_diff_context_finds_callers` (assert on `authenticate`)
- `test_doc_search.py` — negative test: "def authenticate" is not a doc query

Total: ~22 test functions across 10 test files.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Duration | 9,918 ms |
| Tool calls | 5 (1 Bash + 2 Grep + 2 Read) |
| Tokens (est.) | ~8,000 |
| Quality | 5/5 |
| Precision | 95% |

### Process
1. Grep for `def authenticate` across the entire repo -- found it defined in conftest.py fixture and referenced in test_symbol_resolution.py.
2. Grep for `authenticate` in tests/ directory -- found all 22+ references across 10 test files.
3. Read `test_test_mapping.py`, `test_impact_analysis.py`, `test_symbol_resolution.py` for detailed understanding.

### Findings
Identified all 10 test files and ~22 test functions referencing `authenticate`. The broad Grep caught every reference including indirect ones (e.g., `test_doc_search.py` negative test, `test_stale_index.py` file modification). Required manual review of 3 files to confirm the nature of each reference.

---

## Round 2 — Arrow (`get_tests_for`)

| Metric | Value |
|---|---|
| Duration | 8,456 ms |
| Tool calls | 1 |
| Tokens (est.) | ~4,500 |
| Quality | 5/5 |
| Precision | 95% |

### Process
1. Called `get_tests_for(function="authenticate", project="andreasmyleus/arrow")`.

### Findings
Returned "20 found, showing 20/22" -- 20 test functions with full source code across 10 test files. Results included:
- Direct test mapping tests (`test_test_mapping.py`)
- Impact analysis tests (`test_impact_analysis.py`)
- Symbol resolution tests (`test_symbol_resolution.py`)
- Budget tests (`test_budget.py`)
- Conversation dedup test (`test_conversation.py`)
- Frecency boost test (`test_frecency.py`)
- Storage method tests (`test_storage_methods.py`)
- Stale index test (`test_stale_index.py`)
- Diff context tests (`test_diff_context.py`)

Missing 2 of 22 (truncated by display limit). Did not include the `test_doc_search.py` negative test or possibly `test_impact_finds_tests`.

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|---|---|---|---|
| Duration | 9,918 ms | 8,456 ms | Arrow |
| Tool calls | 5 | 1 | Arrow |
| Tokens (est.) | ~8,000 | ~4,500 | Arrow |
| Quality | 5/5 | 5/5 | Tie |
| Precision | 95% | 95% | Tie |
| Completeness | 22/22 refs found | 20/22 shown | Traditional |

### Summary

Both approaches delivered high-quality results. Arrow was faster (15% less time), used 80% fewer tool calls, and returned ~44% fewer tokens while providing inline source code for every matched test. The Traditional approach found all 22 references including edge cases like negative tests, while Arrow's display limit truncated 2 results. For the practical question "what tests cover this function?", Arrow's single-call approach with inline code is clearly more efficient -- the developer gets actionable test code immediately without needing to manually read files.
