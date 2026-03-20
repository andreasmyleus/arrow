# Query 14: Storage Constructor Impact Analysis

**Category:** Impact analysis
**Query:** "If I change the `Storage` class constructor, what breaks?"
**Arrow tool:** `what_breaks_if_i_change`

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Duration | 29,478 ms |
| Tool calls | 10 |
| Tokens (est.) | ~1,400 |
| Quality | 3/5 |
| Precision | 65% |

### Approach
1. Grep for `from.*storage.*import` and `Storage(` across `src/` and `tests/`
2. Read the Storage class constructor to understand the signature
3. Grep for `storage.` usage counts per file to gauge dependency depth
4. Cross-referenced import patterns across all source and test files

### Findings
- Identified 4 source files importing Storage: `server.py`, `indexer.py`, `search.py`, `cli.py`
- Found 4 test files directly constructing Storage: `test_edge_cases.py`, `test_noncode_chunking.py`, `test_core.py`, `test_precision.py`
- Counted `storage.` method calls: server.py (30), indexer.py (47), search.py (11), tools_analysis.py (30), tools_data.py (27)
- Found 16 test files referencing storage in some way (42 total occurrences)
- Did NOT enumerate individual caller functions or produce a structured impact report
- Missed demo scripts (`demo_comparison.py`, `demo_part2.py`) and benchmark files as callers

### Limitations
- Produced file-level counts only, not function-level caller analysis
- No risk assessment or structured impact summary
- Would need many more tool calls to trace individual callers and build a complete picture

## Round 2 — Arrow (`what_breaks_if_i_change`)

| Metric | Value |
|--------|-------|
| Duration | 13,492 ms |
| Tool calls | 1 |
| Tokens (est.) | ~1,800 (response) |
| Quality | 5/5 |
| Precision | 95% |

### Findings
Arrow returned a structured JSON impact report containing:
- **Risk level:** high
- **34 callers** — individual functions/classes that call `Storage()`, including source files (`server.py`, `indexer.py`, `search.py`, `cli.py`), test files (27 test functions/classes across 13 test files), demo scripts, and benchmarks
- **45 affected tests** — every test function that directly references Storage, with file path and test name
- **12 dependent files** — all files that import from storage.py
- Each caller includes file path, function/class name, kind, and which symbol is called

### Limitations
- Some "affected tests" entries reference markdown files (benchmark spec), which are not actual tests
- The test count (45) includes some duplication between callers and affected_tests sections

## Comparison

| Metric | Traditional | Arrow | Factor |
|--------|------------|-------|--------|
| Duration | 29,478 ms | 13,492 ms | 2.2x faster |
| Tool calls | 10 | 1 | 10x fewer |
| Granularity | File-level | Function-level | Arrow far more detailed |
| Callers identified | ~6 files | 34 functions | Arrow 5x more specific |
| Tests identified | ~4 direct | 27 test functions | Arrow much more complete |
| Risk assessment | None | "high" with summary | Arrow only |

## Verdict

Arrow wins decisively on this query. Impact analysis is one of Arrow's strongest use cases — it requires tracing callers, tests, and dependents at the function level, which is extremely tedious with traditional tools. The traditional approach required 10 tool calls and still only produced file-level counts without individual caller enumeration. Arrow produced a complete, structured impact report in a single call at 2.2x the speed, identifying 34 specific caller functions and 27 affected test functions with risk assessment.
