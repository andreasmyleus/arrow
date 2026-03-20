# Query 11: Find the estimate_budget function

**Category:** search_structure — Symbol
**Arrow tool under test:** `search_structure`
**Query:** "Find the estimate_budget function"

## Round 1 — Traditional (Glob / Grep / Read)

| Metric | Value |
|---|---|
| Wall time | 10.6 s |
| Tool calls | 2 |
| Tokens (est.) | ~1,800 |
| Quality | 5/5 |
| Precision | 100% |

**Steps:**
1. `Grep` for `def estimate_budget` — found single match at `search.py:656`
2. `Read` lines 656-695 to get the full function body (36 lines)

## Round 2 — Arrow (search_structure)

| Metric | Value |
|---|---|
| Wall time | 8.2 s |
| Tool calls | 1 |
| Tokens (est.) | ~800 |
| Quality | 5/5 |
| Precision | 100% |

**Results:** Single exact match returned with full source code, file path, line range (656-691), kind (`function`), and project metadata.

## Comparison

| Metric | Traditional | Arrow | Winner |
|---|---|---|---|
| Wall time | 10.6 s | 8.2 s | Arrow |
| Tool calls | 2 | 1 | Arrow |
| Tokens (est.) | ~1,800 | ~800 | Arrow |
| Quality | 5/5 | 5/5 | Tie |
| Precision | 100% | 100% | Tie |

## Analysis

**Arrow was faster** in wall time (8.2s vs 10.6s) and used fewer tool calls (1 vs 2). The single `search_structure` call returned the complete source code with precise line range (656-691) and kind classification (`function`), eliminating the need for a follow-up Read.

Traditional required two steps: Grep to locate the definition, then Read to retrieve the full function body. Both approaches achieved perfect precision and quality for this single-definition symbol.

For exact symbol lookups, Arrow's AST-based structure index is a natural fit -- it returns the complete definition in one call with useful metadata (kind, line range, project). The token savings (~56% fewer) come from not needing a separate Read tool call with surrounding context lines.
