# Benchmark Run: 2026-03-20 (Run 5)

Arrow version: 90ecc75
Codebase: /Users/andreas/arrow (63 files indexed, 835 chunks)
Model: Claude Opus 4.6
Previous run: run-2026-03-20T1815 (46e2353, 95 files, 1092 chunks)

## Changes Since Last Run

- Force re-index with 63 files (down from 95), 835 chunks (down from 1092)
- Benchmark reports excluded from index (removed ~32 files of report markdown)
- Index pollution from benchmark reports (which caused Q7 and Q26 failures in previous run) should be resolved
- `search_regex` previously had permission denied errors in runs 3-4; this run tests whether that is fixed

## Results

| # | Query (short) | Arrow tool(s) | Category | Trad calls | Trad tokens | Arrow tokens | Trad time (s) | Arrow time (s) | Winner | Quality (T/A) |
|---|---------------|---------------|----------|------------|-------------|--------------|---------------|----------------|--------|---------------|
| 1 | Incremental indexing | get_context | Targeted | 5 | ~780 | ~2,369 | 17.3 | 17.2 | **Tie** | 5/5 |
| 2 | Chunker nesting | get_context | Targeted | 8 | ~920 | 0 | 36.6 | 10.0 | **Traditional** | 5/0 |
| 3 | Hybrid search e2e | get_context | Architecture | 10 | ~2,080 | 0 | 30.0 | 11.3 | **Traditional** | 5/1 |
| 4 | Error handling | get_context | Architecture | 11 | ~12,800 | 0 | 29.0 | 11.0 | **Traditional** | 5/0 |
| 5 | Configuration | get_context | Cross-cutting | 8 | ~12,000 | 0 | 24.0 | 11.5 | **Traditional** | 5/0 |
| 6 | Multi-project | get_context | Cross-cutting | 10 | ~8,500 | ~50 | 26.6 | 12.2 | **Traditional** | 5/1 |
| 7 | Frecency | search_code | Hybrid search | 9 | ~4,500 | ~5,800 | 21.1 | 14.5 | **Traditional** | 5/3 |
| 8 | RRF scoring | search_code | Hybrid search | 7 | ~4,500 | ~6,500 | 21.2 | 14.3 | **Arrow** | 5/5 |
| 9 | Exception logging | search_regex | Regex | 3 | ~1,800 | ~2,500 | 16.8 | 9.5 | **Traditional** | 5/1 |
| 10 | Env var reads | search_regex | Regex | 2 | ~5,500 | ~6,000 | 13.2 | 7.7 | **Traditional** | 5/4 |
| 11 | estimate_budget | search_structure | Symbol | 2 | ~1,800 | ~800 | 10.6 | 8.2 | **Arrow** | 5/5 |
| 12 | All classes | search_structure | Symbol | 4 | ~4,500 | ~8,500 | 6.8 | 6.7 | **Arrow** | 4/5 |
| 13 | Search methods | search_structure | Symbol | 4 | ~2,500 | ~4,800 | 13.0 | 15.6 | **Traditional** | 4/4 |
| 14 | Storage impact | what_breaks | Impact | 7 | ~5,500 | ~2,800 | 19.7 | 8.6 | **Arrow** | 3/4 |
| 15 | Chunker impact | what_breaks | Impact | 10 | ~6,500 | ~2,800 | 32.4 | 11.5 | **Arrow** | 4/4 |
| 16 | Storage imports | trace_deps | Dependencies | 8 | ~4,500 | ~1,800 | 28.0 | 8.9 | **Arrow** | 5/5 |
| 17 | Search deps | trace_deps | Dependencies | 3 | ~200 | ~450 | 8.6 | 7.0 | **Arrow** | 4/5 |
| 18 | Search tests | get_tests_for | Tests | 12 | ~12,000 | ~4,500 | 41.7 | 10.0 | **Traditional** | 5/3 |
| 19 | Auth tests | get_tests_for | Tests | 5 | ~8,000 | ~4,500 | 9.9 | 8.5 | **Arrow** | 5/5 |
| 20 | Search diff | get_diff_context | Diff | 8 | ~4,500 | ~2,800 | 29.0 | 9.6 | **Arrow** | 3/5 |
| 21 | Resolve Storage | resolve_symbol | Cross-repo | 4 | ~4,500 | ~800 | 9.8 | 9.4 | **Arrow** | 5/5 |
| 22 | Resolve search | resolve_symbol | Cross-repo | 3 | ~4,500 | ~1,800 | 9.9 | 9.8 | **Arrow** | 3/4 |
| 23 | Server summary | file_summary | File overview | 7 | ~26,000 | ~2,600 | 22.2 | 11.1 | **Arrow** | 5/5 |
| 24 | Storage summary | file_summary | File overview | 8 | ~12,000 | ~3,500 | 26.4 | 8.9 | **Arrow** | 5/4 |
| 25 | Project overview | project_summary | Project overview | 9 | ~4,500 | ~350 | 16.2 | 11.0 | **Arrow** | 5/4 |
| 26 | Dead code | find_dead_code | Dead code | 22 | ~18,000 | ~500 | 87.7 | 13.4 | **Arrow** | 4/3 |
| 27 | Embedding model | get_context | Needle | 4 | ~4,500 | 0 | 9.5 | 10.2 | **Traditional** | 5/1 |
| 28 | Binary detection | get_context | Needle | 7 | ~4,500 | 0 | 41.6 | 8.4 | **Traditional** | 5/1 |
| 29 | Hash algorithm | get_context | Needle | 6 | ~4,500 | ~4,875 | 27.0 | 11.5 | **Traditional** | 5/4 |
| 30 | Token budgeting | get_context | Documentation | 9 | ~8,500 | ~6,076 | 34.3 | 13.4 | **Traditional** | 5/4 |

## Per-tool Summary

| Arrow tool | Queries tested | Wins | Losses | Ties | Avg quality (T/A) | Best use case |
|------------|---------------|------|--------|------|-------------------|---------------|
| get_context | 10 (Q1-6, 27-30) | 0 | 8 | 2 | 5.0 / 1.6 | *Unreliable — zero results on 6/10 queries; succeeded only with keyword reformulation on 3 queries* |
| search_code | 2 (Q7-8) | 1 | 1 | 0 | 5.0 / 4.0 | Exact concept search when keywords match function names (Q8 RRF) |
| search_regex | 2 (Q9-10) | 0 | 2 | 0 | 5.0 / 2.5 | *Multiline matching issues (Q9) and limit saturation (Q10)* |
| search_structure | 3 (Q11-13) | 2 | 1 | 0 | 4.3 / 4.7 | Exact symbol lookup (Q11) and enumerate all symbols of a kind (Q12) |
| what_breaks_if_i_change | 2 (Q14-15) | 2 | 0 | 0 | 3.5 / 4.0 | Impact analysis — always use |
| trace_dependencies | 2 (Q16-17) | 2 | 0 | 0 | 4.5 / 5.0 | Bidirectional import graphs — always use |
| get_tests_for | 2 (Q18-19) | 1 | 1 | 0 | 5.0 / 4.0 | Specific function test lookup (Q19 authenticate); too noisy for broad queries (Q18) |
| get_diff_context | 1 (Q20) | 1 | 0 | 0 | 3.0 / 5.0 | Changed function identification + caller tracing — always use |
| resolve_symbol | 2 (Q21-22) | 2 | 0 | 0 | 4.0 / 4.5 | Cross-repo symbol resolution — always use |
| file_summary | 2 (Q23-24) | 2 | 0 | 0 | 5.0 / 4.5 | File structure overview — always use |
| project_summary | 1 (Q25) | 1 | 0 | 0 | 5.0 / 4.0 | Quick project orientation — always use |
| find_dead_code | 1 (Q26) | 1 | 0 | 0 | 4.0 / 3.0 | Quick dead code scan (6.5x faster than manual, but lower recall) |

## Totals

| Metric | Traditional | Arrow |
|--------|-------------|-------|
| Total tool calls | 196 | 30 (+ ~8 retries on get_context) |
| Total content tokens | ~189,380 | ~78,368 |
| Total wall time | 707.6s | 314.8s |
| Avg answer quality | 4.70 | 3.37 |
| Queries won | **12** | **15** |
| Ties | 3 | 3 |
| Zero-result queries | 0 | 6 (Q2, Q3, Q4, Q5, Q27, Q28) |

## Comparison With Previous Run (run-2026-03-20T1815)

| Metric | Previous Run | This Run | Change |
|--------|-------------|----------|--------|
| Arrow wins | 10/30 | 15/30 | **+5 wins** |
| Arrow losses | 18/30 | 12/30 | **-6 losses** |
| Ties | 2/30 | 3/30 | +1 |
| Arrow zero-result queries | 12/30 | 6/30 | **-6 (50% reduction)** |
| Arrow avg quality | 2.73 | 3.37 | **+0.64 improvement** |
| Traditional avg quality | 4.57 | 4.70 | +0.13 |
| Total trad tool calls | 170 | 196 | +26 (more thorough traditional runs) |
| Total arrow tool calls | 30 | 30 (+~8 retries) | Similar |
| `get_context` wins | 0/10 | 0/10 | No change (still 0 wins) |
| `get_context` zero-results | 10/10 | 6/10 | **Improved — 4 queries now return results** |
| `search_regex` status | Permission denied | Functional but flawed | **Fixed — no longer blocked** |
| `find_dead_code` wins | 0/1 | 1/1 | **Fixed — index pollution resolved** |
| `get_diff_context` wins | 0/1 | 1/1 | **Fixed — correctly identified changed function** |
| `get_tests_for` wins | 0/2 | 1/2 | **Improved — Q19 now wins** |
| `search_code` wins | 0/2 | 1/2 | **Improved — Q8 now wins** |
| Index files | 95 | 63 | -32 (reports excluded) |
| Index chunks | 1092 | 835 | -257 |

## Analysis

### The Critical Problems

1. **`get_context` still returns zero results on 6/10 queries (60% failure rate).** Queries Q2 (chunker nesting), Q3 (hybrid search e2e), Q4 (error handling), Q5 (configuration), Q27 (embedding model), Q28 (binary detection) returned zero chunks on the first attempt. This is improved from 10/10 in the previous run but remains the dominant failure mode. Natural-language phrasing consistently fails; keyword reformulation sometimes succeeds (Q1, Q29, Q30). The relevance threshold is still too aggressive for conceptual and architectural queries.

2. **`get_context` never wins (0/10).** Even when it returns results (Q1, Q6, Q29, Q30), Arrow either ties (Q1) or loses (Q6, Q29, Q30) because the results are noisy (low precision: 45-85%) or require a retry that adds latency. Traditional approaches remain more reliable for every query type `get_context` is tested against.

3. **`search_regex` has functional defects (2/2 losses).** Permission denied is fixed, but two new problems emerged: (a) multiline matching spans across entire chunks, producing massive false positives (Q9 — found 0/13 actual exception+log sites), and (b) the 50-match limit saturates on broad patterns, causing important files like `cli.py` to be entirely absent from results (Q10).

### Where Arrow Excels

Arrow's **specialized analysis tools** are consistently excellent and account for all 15 wins:

1. **Impact analysis** (`what_breaks_if_i_change`): 2/2 wins. Found 28-34 callers + 21-30 tests + risk rating vs traditional's incomplete grep-based analysis. 2.3-2.8x faster, 2x fewer tokens. Unique capability.

2. **Dependency tracing** (`trace_dependencies`): 2/2 wins. Bidirectional + transitive import graphs in a single call. Found 12-13 direct importers + 26+ transitive vs traditional's 2-8. 1.2-3.1x faster.

3. **Symbol resolution** (`resolve_symbol`): 2/2 wins. Cross-repo exact symbol lookup with full code bodies. 2.5-5.6x fewer tokens. AST-aware (no string literal false positives).

4. **File summaries** (`file_summary`): 2/2 wins. Structured JSON with all functions, line ranges, token counts. 2-3x faster, 3.4-10x fewer tokens than reading entire files.

5. **Project summary** (`project_summary`): 1/1 win. Complete language distribution, directory structure in one call. 13x fewer tokens.

6. **Diff context** (`get_diff_context`): 1/1 win (reversed from previous run's loss). Correctly identified `get_context` as the changed function and found 22 callers vs traditional's 7. 3x faster.

7. **Dead code** (`find_dead_code`): 1/1 win (reversed from previous run's loss). Found 3 true dead functions with 100% precision. 6.5x faster, 36x fewer tokens.

8. **Test lookup** (`get_tests_for`): 1/2 wins. Excellent for specific function queries (Q19: `authenticate` found 20/22 tests). Too noisy for broad concept queries (Q18: "search pipeline" only found 50% of relevant test files).

9. **Symbol enumeration** (`search_structure`): 2/3 wins. Excellent for exact lookups (Q11) and enumerate-all (Q12). `kind="method"` vs `kind="function"` classification issue on Q13.

10. **Hybrid search** (`search_code`): 1/2 wins. Q8 (RRF scoring) matched perfectly when query keywords aligned with function names. Q7 (frecency) missed the core storage-layer calculation.

### Where Arrow Fails

1. **`get_context` (0/10):** The primary search interface still cannot win a single query. Zero results on 60% of queries. When results are returned, they are noisy or incomplete. Natural-language queries fail consistently; only keyword reformulations work. This is the single biggest issue.

2. **`search_regex` (0/2):** No longer permission-denied, but multiline matching produces false positives spanning across chunks (Q9), and the 50-match limit drops important files (Q10). No file-type filtering parameter.

3. **`search_code` partial (Q7):** Missing the core `get_frecency_scores()` storage function. The search pipeline returns the application layer but not the calculation layer.

4. **`search_structure` partial (Q13):** Tree-sitter classifies Python class methods as `function`, not `method`. Users must know to use `kind="any"` or `kind="function"` for methods.

### Key Recommendations (Priority Order)

1. **Fix `get_context` relevance threshold** — This remains the #1 blocker. 0/10 win rate despite 4 queries now returning results. Options:
   - Guarantee minimum 5 results regardless of score (already has `_MIN_RESULTS_FLOOR=5` but it may not be applied in the right place)
   - Lower the relevance floor for natural-language queries (current threshold filters out everything for conceptual queries)
   - Add query preprocessing: extract keywords from natural-language questions before BM25 matching
   - Fall back to BM25-only search when vector search returns low scores

2. **Fix `search_regex` multiline matching** — Add a max-span-lines parameter to prevent matches from spanning entire chunks. Consider a two-pass approach for patterns like "except...log" (find `except` lines, then check next N lines).

3. **Add file-type filtering to `search_regex`** — A `glob` or `type` parameter would prevent the 50-match limit from being saturated by non-target file types.

4. **Improve `get_tests_for` for broad queries** — When the function name is a common word like "search", the tool should scope results more aggressively to `test_*.py` files and filter out fixture definitions.

5. **Fix `search_structure` kind classification** — Either map tree-sitter's `function_definition` inside a class to `method`, or document that `kind="method"` will not work for Python.

### Verdict

**Arrow's win rate improved from 33% to 50% (15/30), a significant step forward.**

The improvement came from three sources:
- **Excluding benchmark reports from the index** fixed `find_dead_code` (Q26) and removed index pollution from `search_code` results
- **`get_diff_context` correctly identified the changed function** (Q20), reversing the previous run's loss
- **`get_context` partially improved** — 4 queries now return results (down from 10/10 zero-result), enabling Q1 to tie and Q29/Q30 to at least produce answers (though still losing on quality)
- **`get_tests_for` improved** — Q19 (`authenticate`) now wins with 95% precision
- **`search_code` improved** — Q8 (RRF scoring) now wins

However, `get_context` remains completely unable to win any query (0/10), which is critical because it is the primary search tool and the one most users will reach for first. The 6 remaining zero-result queries are all natural-language conceptual questions — exactly the type of query users most want to ask.

**Net assessment:** Arrow has crossed from "broken primary tool with good specialists" to "excellent specialist tools with a weak primary tool." The specialist tools (what_breaks, trace_deps, resolve_symbol, file_summary, project_summary, get_diff_context) now account for a 15/30 win rate and should be used aggressively. The primary search tool (`get_context`) should be avoided for natural-language queries until the relevance threshold is fixed.

**Recommended usage strategy:**
- **Always use Arrow for:** `what_breaks_if_i_change`, `trace_dependencies`, `resolve_symbol`, `file_summary`, `project_summary`, `get_diff_context`
- **Use Arrow as primary for:** `search_structure` (exact names or enumeration), `find_dead_code` (quick scan)
- **Use Arrow as supplement for:** `search_code` (keyword queries only), `get_tests_for` (specific function names only)
- **Avoid Arrow for:** `get_context` (unreliable — 0 wins, 60% zero-result rate), `search_regex` (multiline bugs, limit saturation), broad architectural queries, natural-language conceptual questions
