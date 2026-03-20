# Query 11: Find the estimate_budget function

**Category:** search_structure — AST symbol lookup
**Date:** 2026-03-20T15:30

## Query
"Find the estimate_budget function"

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 8,827 ms |
| Tool calls | 2 (Grep, Read) |
| Result | Found `estimate_budget` at `src/arrow/search.py:631-666` |
| Quality | 5/5 |
| Precision | 100% |

**Steps:**
1. `Grep` for `def estimate_budget` — found single match at `search.py:631`
2. `Read` lines 631-680 to get the full function body

## Round 2 — Arrow (search_structure)

| Metric | Value |
|---|---|
| Wall time | 20,109 ms |
| Tool calls | 1 (search_structure) |
| Results returned | 1 |
| Result | Found `estimate_budget` at `src/arrow/search.py:631-666` with full source |
| Quality | 5/5 |
| Precision | 100% |

**Steps:**
1. `search_structure(symbol="estimate_budget", project="andreasmyleus/arrow")` — returned exact match with full source code

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time (ms) | 8,827 | 20,109 |
| Tool calls | 2 | 1 |
| Precision | 100% | 100% |
| Quality | 5/5 | 5/5 |
| Complete source returned | Partial (needed Read) | Yes (included in result) |

## Analysis

Both approaches found the exact same function at `src/arrow/search.py:631-666` with 100% precision.

**Traditional** was faster in wall time (8.8s vs 20.1s). Grep is extremely efficient for exact pattern matching like `def estimate_budget`, and the two-step flow (Grep to locate, Read to retrieve) completed quickly.

**Arrow** used fewer tool calls (1 vs 2) and returned the complete source code in a single response, including precise line range metadata and kind classification (`function`). The higher wall time is likely due to MCP overhead and the AST index lookup.

For simple "find this exact function" queries, traditional Grep is faster and equally precise. Arrow's advantage is the richer metadata (kind, project, exact line range) and single-call convenience, which matters more for ambiguous or partial symbol names.
