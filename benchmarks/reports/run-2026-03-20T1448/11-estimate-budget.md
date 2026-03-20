# Query 11: Find the `estimate_budget` function

**Category:** Symbol
**Arrow tool(s):** `search_structure`
**Timestamp:** 2026-03-20T14:48

## Round 1 — Traditional (Glob / Grep / Read)

| Metric | Value |
|--------|-------|
| Wall time | 11.4s |
| Tool calls | 2 |
| Tokens (est.) | ~200 |
| Quality | 5/5 |
| Precision | 100% |

**Steps:**
1. `Grep` for `def estimate_budget` — found single match at `search.py:656`
2. `Read` lines 656-705 to get the full function body (36 lines)

## Round 2 — Arrow (search_structure)

| Metric | Value |
|--------|-------|
| Wall time | 7.1s |
| Tool calls | 1 |
| Tokens (est.) | ~144 |
| Chunks returned | 1 |
| Quality | 5/5 |
| Precision | 100% |

**Steps:**
1. `search_structure(symbol="estimate_budget", kind="function", project="andreasmyleus/arrow")` — returned exact match at `search.py:656-691` with full source code

## Analysis

Both approaches achieved perfect results: the single `estimate_budget` method in `src/arrow/search.py` at lines 656-691.

**Arrow was faster** (7.1s vs 11.4s) and used fewer tool calls (1 vs 2). The AST index returned the precise line range and complete source in one call, whereas traditional required a Grep to locate the function followed by a Read to retrieve it.

**Token efficiency:** Arrow returned ~144 tokens (just the function body), while traditional returned ~200 tokens (the function plus extra context lines from the Read overshoot).

This is the ideal case for `search_structure` — a known symbol name with a specific kind filter. The AST index provides an exact match with zero noise.

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time | 11.4s | 7.1s | Arrow |
| Tool calls | 2 | 1 | Arrow |
| Tokens | ~200 | ~144 | Arrow |
| Quality | 5/5 | 5/5 | Tie |
| Precision | 100% | 100% | Tie |
