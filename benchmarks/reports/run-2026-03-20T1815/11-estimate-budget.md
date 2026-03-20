# Query 11: Find the `estimate_budget` function

**Category:** Symbol lookup
**Query:** "Find the `estimate_budget` function"
**Arrow tool:** `search_structure`

## Round 1 — Traditional (Glob / Grep / Read)

| Metric | Value |
|---|---|
| Wall time | 7,708 ms |
| Tool calls | 2 (Grep, Read) |
| Lines read | ~65 |
| Tokens (est.) | ~260 |
| Quality | 5/5 |
| Precision | 100% |

**Steps:**
1. `Grep` for `def estimate_budget` — found single match at `search.py:656`
2. `Read` lines 656-705 to get the full function body

## Round 2 — Arrow (search_structure)

| Metric | Value |
|---|---|
| Wall time | 10,026 ms |
| Tool calls | 1 (search_structure) |
| Results returned | 1 |
| Result | Found `estimate_budget` at `src/arrow/search.py:656-691` with full source |
| Quality | 5/5 |
| Precision | 100% |

**Steps:**
1. `search_structure(symbol="estimate_budget", project="andreasmyleus/arrow")` — returned exact match with full source code

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 7,708 ms | 10,026 ms |
| Tool calls | 2 | 1 |
| Tokens consumed | ~260 | ~260 |
| Quality | 5/5 | 5/5 |
| Precision | 100% | 100% |

## Analysis

**Traditional was faster** in wall time (7.7s vs 10.0s). Grep is extremely efficient for exact pattern matching like `def estimate_budget`, and the two-step flow (Grep to locate, Read to retrieve) completed quickly.

**Arrow** used fewer tool calls (1 vs 2) and returned the complete source code in a single response with precise line range metadata (656-691) and kind classification (`function`). The higher wall time is due to MCP round-trip overhead and AST index lookup.

For simple "find this exact function" queries, traditional Grep is faster and equally precise. Arrow's advantage is the richer metadata (kind, project, exact line range) and single-call convenience, which matters more for ambiguous or partial symbol names.
