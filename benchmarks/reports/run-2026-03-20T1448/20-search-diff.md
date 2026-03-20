# Query 20: What functions changed in search.py and who calls them?

**Category:** Diff
**Arrow tool(s):** `get_diff_context`
**Date:** 2026-03-20

## Note on Working Tree State

No uncommitted changes existed in `search.py`. Both rounds analyzed the most
recent commit touching the file (`63d8e98`), which removed the second-pass
relevance filtering from `get_context`.

---

## Round 1 — Traditional (Glob + Grep + Read + Bash)

| Metric | Value |
|--------|-------|
| Wall time | 32,178 ms |
| Tool calls | 8 (Bash x4, Read x2, Grep x2) |
| Lines read | ~92 |
| Tokens (est.) | ~368 |
| Quality | 3/5 |
| Precision | 75% |

### Approach
1. `git diff` to check uncommitted changes (none found)
2. `git log` to find last commit touching search.py
3. `git diff 63d8e98~1..63d8e98` to get the actual diff
4. `Read` to identify the containing function (`get_context`)
5. `Grep` for `\.get_context\(` across the codebase

### Findings
- **Changed function:** `get_context` (lines 693-784) in `HybridSearcher`
- **Change:** Removed second-pass relevance filtering (score floor + cliff
  detection), trusting `filter_by_relevance()` in `search()` instead
- **Callers found:** 16 call sites across 9 files (src/arrow/cli.py,
  src/arrow/server.py, benchmarks/, demo_comparison.py, tests/)

### Limitations
- Required 4 sequential steps before caller search could even begin
- Grep found direct `.get_context(` calls only — missed indirect dependents
- No dependency graph or test coverage information
- Manual function identification from line numbers

---

## Round 2 — Arrow (`get_diff_context`)

| Metric | Value |
|--------|-------|
| Wall time | 11,241 ms |
| Tool calls | 1 |
| Tokens returned | ~1,800 (full function + 22 callers + 13 dependents) |
| Quality | 5/5 |
| Precision | 95% |

### Approach
Single call: `get_diff_context(file="src/arrow/search.py", ref="63d8e98", project="andreasmyleus/arrow")`

### Findings
- **Changed function:** `get_context` (lines 693-784) — full source returned
- **Callers:** 22 caller functions across 12 files, each with function name,
  line range, and file path
- **Dependent files:** 13 files in the dependency graph (includes transitive
  dependents like `test_search_regex.py`, `test_noncode_chunking.py`,
  `vector_store.py` that don't directly call `get_context`)

### Additional callers found vs Traditional
Arrow found callers in files that grep missed because they reference
`get_context` through fixtures, indirect imports, or function-level wrapping:
- `demo_part2.py` (nested call inside `p()`)
- `tests/test_doc_search.py` (via fixture `project_with_readme`)
- `tests/test_conversation.py`
- `tests/test_tool_chain.py` (large integration test)
- Additional `test_budget.py` functions (7 vs grep's 3)

---

## Comparison

| Metric | Traditional | Arrow | Factor |
|--------|------------|-------|--------|
| Wall time (ms) | 32,178 | 11,241 | **2.9x faster** |
| Tool calls | 8 | 1 | **8x fewer** |
| Callers found | 16 sites / 9 files | 22 callers / 12 files | **+38% coverage** |
| Dependent files | 0 | 13 | Arrow-only |
| Full function body | No (manual read) | Yes (auto-included) | Arrow-only |
| Quality | 3/5 | 5/5 | |
| Precision | 75% | 95% | |

## Verdict

**Arrow wins decisively.** `get_diff_context` is purpose-built for this query
pattern: one call returns the changed function's full source, all callers with
context, and the transitive dependency graph. The traditional approach required
8 sequential tool calls, manual function identification from line offsets, and
still missed ~6 callers and all transitive dependents. The 2.9x speed advantage
understates Arrow's value here — the real win is completeness of the impact
analysis, which is critical for safe refactoring.
