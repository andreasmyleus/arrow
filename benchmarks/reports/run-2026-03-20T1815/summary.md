# Benchmark Run: 2026-03-20 (Run 3)

Arrow version: 46e2353
Codebase: /Users/andreas/arrow (95 files indexed, 1092 chunks)
Model: Claude Opus 4.6
Previous run: run-2026-03-20T1530 (2de47a1, 63 files, 828 chunks)

## Changes Since Last Run

- Force re-index with 95 files (up from 63), 1092 chunks (up from 828)
- Recent commits: multiline regex support, enumerate mode for search_structure, ref parameter for get_diff_context

## Results

| # | Query (short) | Arrow tool(s) | Category | Trad calls | Trad tokens | Arrow tokens | Trad time (s) | Arrow time (s) | Winner | Quality (T/A) |
|---|---------------|---------------|----------|------------|-------------|--------------|---------------|----------------|--------|---------------|
| 1 | Docker setup | get_context | Targeted | 7 | ~304 | 0 | 6.9 | 8.8 | **Traditional** | 5/0 |
| 2 | CI pipeline | get_context | Targeted | 4 | ~204 | 0 | 7.1 | 9.4 | **Traditional** | 5/1 |
| 3 | Hybrid search e2e | get_context | Architecture | 11 | ~2,540 | 0 | 54.7 | 9.7 | **Traditional** | 5/1 |
| 4 | Error handling | get_context | Architecture | 8 | ~1,240 | 0 | 25.9 | 13.8 | **Traditional** | 5/1 |
| 5 | Configuration | get_context | Cross-cutting | 8 | ~5,576 | 0 | 18.1 | 8.7 | **Traditional** | 5/1 |
| 6 | Multi-project | get_context | Cross-cutting | 9 | ~1,200 | 0 | 24.0 | 12.4 | **Traditional** | 5/0 |
| 7 | Frecency | search_code | Hybrid search | 10 | ~1,120 | ~4,500 | 16.3 | 7.3 | **Traditional** | 5/2 |
| 8 | RRF scoring | search_code | Hybrid search | 7 | ~1,040 | ~3,200 | 21.8 | 8.0 | **Tie** | 5/5 |
| 9 | Exception logging | search_regex | Regex | 2 | ~620 | 0 | 12.0 | 17.8 | **Traditional** | 5/0 |
| 10 | Env var reads | search_regex | Regex | 3 | ~280 | 0 | 13.7 | 8.4 | **Traditional** | 5/1 |
| 11 | estimate_budget | search_structure | Symbol | 2 | ~260 | ~260 | 7.7 | 10.0 | **Tie** | 5/5 |
| 12 | All classes | search_structure | Symbol | 1 | ~72 | ~3,500 | 5.8 | 13.1 | **Arrow** | 3/5 |
| 13 | Search methods | search_structure | Symbol | 2 | ~144 | ~2,500 | 7.6 | 10.3 | **Traditional** | 4/4 |
| 14 | Storage impact | what_breaks | Impact | 10 | ~1,400 | ~1,800 | 29.5 | 13.5 | **Arrow** | 3/5 |
| 15 | Chunker impact | what_breaks | Impact | 7 | ~1,200 | ~2,500 | 23.6 | 8.2 | **Arrow** | 4/4 |
| 16 | Storage imports | trace_deps | Dependencies | 4 | ~480 | ~450 | 24.2 | 11.2 | **Arrow** | 4/4 |
| 17 | Search deps | trace_deps | Dependencies | 1 | ~240 | ~350 | 4.5 | 6.2 | **Arrow** | 4/5 |
| 18 | Search tests | get_tests_for | Tests | 7 | ~2,200 | ~8,000 | 20.4 | 11.5 | **Traditional** | 5/4 |
| 19 | Auth tests | get_tests_for | Tests | 5 | ~740 | ~5,000 | 12.1 | 7.9 | **Traditional** | 4/3 |
| 20 | Search diff | get_diff_context | Diff | 8 | ~400 | ~1,200 | 26.4 | 13.8 | **Traditional** | 5/3 |
| 21 | Resolve Storage | resolve_symbol | Cross-repo | 4 | ~100 | ~30 | 11.1 | 9.9 | **Arrow** | 5/5 |
| 22 | Resolve search | resolve_symbol | Cross-repo | 6 | ~800 | ~600 | 18.2 | 8.4 | **Arrow** | 3/4 |
| 23 | Server summary | file_summary | File overview | 8 | ~4,676 | ~800 | 21.6 | 16.0 | **Arrow** | 5/5 |
| 24 | Storage summary | file_summary | File overview | 8 | ~5,660 | ~2,800 | 28.3 | 7.7 | **Arrow** | 5/4 |
| 25 | Project overview | project_summary | Project overview | 11 | ~1,200 | ~350 | 20.7 | 8.8 | **Arrow** | 4/5 |
| 26 | Dead code | find_dead_code | Dead code | 12 | ~1,400 | ~30 | 77.8 | 12.1 | **Traditional** | 3/2 |
| 27 | Embedding model | get_context | Needle | 4 | ~940 | 0 | 10.7 | 9.3 | **Traditional** | 5/0 |
| 28 | Docker healthcheck | get_context | Needle | 6 | ~244 | 0 | 9.2 | 5.8 | **Traditional** | 5/1 |
| 29 | Hash algorithm | get_context | Needle | 5 | ~340 | 0 | 12.9 | 13.2 | **Traditional** | 5/1 |
| 30 | MCP tools list | get_context | Documentation | 2 | ~1,840 | 0 | 5.7 | 8.5 | **Traditional** | 5/1 |

## Per-tool Summary

| Arrow tool | Queries tested | Wins | Losses | Ties | Avg quality (T/A) | Best use case |
|------------|---------------|------|--------|------|-------------------|---------------|
| get_context | 10 (Q1-6, 27-30) | 0 | 10 | 0 | 5.0 / 0.6 | *None — zero results on all 10 queries* |
| search_code | 2 (Q7-8) | 0 | 1 | 1 | 5.0 / 3.5 | Exact symbol/concept search (Q8 tied) |
| search_regex | 2 (Q9-10) | 0 | 2 | 0 | 5.0 / 0.5 | *Permission denied — could not evaluate* |
| search_structure | 3 (Q11-13) | 1 | 1 | 1 | 4.0 / 4.7 | Enumerate all symbols of a kind (Q12) |
| what_breaks_if_i_change | 2 (Q14-15) | 2 | 0 | 0 | 3.5 / 4.5 | Impact analysis — always use |
| trace_dependencies | 2 (Q16-17) | 2 | 0 | 0 | 4.0 / 4.5 | Bidirectional import graphs — always use |
| get_tests_for | 2 (Q18-19) | 0 | 2 | 0 | 4.5 / 3.5 | Specific function test lookup (broad queries noisy) |
| get_diff_context | 1 (Q20) | 0 | 1 | 0 | 5.0 / 3.0 | Diff analysis (misidentified changed function) |
| resolve_symbol | 2 (Q21-22) | 2 | 0 | 0 | 4.0 / 4.5 | Cross-repo symbol resolution — always use |
| file_summary | 2 (Q23-24) | 2 | 0 | 0 | 5.0 / 4.5 | File structure overview — always use |
| project_summary | 1 (Q25) | 1 | 0 | 0 | 4.0 / 5.0 | Quick project orientation — always use |
| find_dead_code | 1 (Q26) | 0 | 1 | 0 | 3.0 / 2.0 | Missed real dead code (LIKE false negatives) |

## Totals

| Metric | Traditional | Arrow |
|--------|-------------|-------|
| Total tool calls | 170 | 30 |
| Total content tokens | ~36,460 | ~37,870 |
| Total wall time | 572.0s | 298.3s |
| Avg answer quality | 4.57 | 2.73 |
| Queries won | **18** | **10** |
| Ties | 2 | 2 |
| Zero-result queries | 0 | 12 |

## Comparison With Previous Run (run-2026-03-20T1530)

| Metric | Previous Run | This Run | Change |
|--------|-------------|----------|--------|
| Arrow wins | 10/30 | 10/30 | No change |
| Arrow losses | 20/30 | 18/30 | +2 ties (Q8, Q11) |
| Arrow zero-result queries | 11/30 | 12/30 | Slightly worse |
| Arrow avg quality | 2.76 | 2.73 | Slightly worse |
| Traditional avg quality | 4.40 | 4.57 | Improved |
| Total trad tool calls | 169 | 170 | No change |
| Total arrow tool calls | 56 | 30 | Fewer (better) |
| `get_context` wins | 0/10 | 0/10 | No change |
| `search_structure` wins | 1/3 | 1/3 | No change (enumerate mode worked for Q12) |
| `find_dead_code` wins | 1/1 | 0/1 | Regressed — LIKE false negatives from indexed reports |
| `search_regex` permission | Denied | Denied | Still broken |
| Index pollution from reports | Not observed | Observed (Q7) | New problem |

## Analysis

### The Critical Problems

1. **`get_context` returns zero results (10/10 queries, 100% failure rate).** Every single `get_context` query returned zero chunks. This is Arrow's primary search interface and it is completely non-functional. The relevance threshold filters out all results regardless of query type — targeted lookups, architectural questions, needle-in-haystack, documentation queries. This single bug accounts for 10 of Arrow's 18 losses.

2. **`search_regex` is inaccessible (2/2 queries, permission denied).** Both regex queries (Q9, Q10) were denied at runtime. The tool cannot be evaluated at all.

3. **Index pollution from benchmark reports (Q7).** The previous run's benchmark reports are now indexed, and their natural-language descriptions of code rank higher than actual source code for keyword queries like "frecency." All 10 chunks returned for Q7 were from `benchmarks/reports/` markdown, zero from source code.

4. **`find_dead_code` regressed (Q26).** Previously found dead code; now returns zero results. The `LIKE %name%` heuristic gets false negatives because function names appear in indexed benchmark report text, satisfying the reference check without being actual callers.

### Where Arrow Excels

Arrow's **specialized analysis tools** remain excellent and unchanged from the previous run:

1. **Impact analysis** (`what_breaks_if_i_change`): 2/2 wins. Found 34 callers + 45 tests + risk rating (Q14) vs traditional's file-level counts only. 2.2-2.9x faster. Unique capability with no traditional equivalent.

2. **Dependency tracing** (`trace_dependencies`): 2/2 wins. Bidirectional + transitive import graphs in a single call. Traditional can only do forward imports by reading source headers.

3. **Symbol resolution** (`resolve_symbol`): 2/2 wins. Cross-repo exact symbol lookup with full code bodies. Traditional requires manually grepping each repo directory.

4. **File summaries** (`file_summary`): 2/2 wins. Structured JSON with all functions, line ranges, token counts. 1.3-3.7x faster, 2-5.8x fewer tokens than reading entire files.

5. **Project summary** (`project_summary`): 1/1 win. Complete language distribution, directory structure, entry points in one call. Traditional missed half the repo (entire benchmarks/ directory).

6. **Class enumeration** (`search_structure` with `kind="class"`): 1/1 win (Q12). Found all 68 classes including test classes and nested classes. Traditional grep found only 18 in `src/arrow/`.

### Where Arrow Fails

1. **`get_context` (0/10):** Zero results on every query. The relevance threshold is catastrophically aggressive. Same failure mode as previous run — no improvement.

2. **`search_regex` (0/2):** Permission denied at runtime. Cannot evaluate the tool at all.

3. **`search_code` (0/1 loss, 1/1 tie):** Index pollution caused Q7 failure (benchmark reports outranking source code). Q8 tied because the query terms closely matched function names.

4. **`get_tests_for` (0/2):** Too broad — returns all chunks mentioning the function name (36-74 results with ~5,000-8,000 tokens) including fixture definitions, benchmark docs, and incidental references. Low precision (45-75%).

5. **`get_diff_context` (0/1):** Misidentified the changed function (attributed change to `_is_doc_path` instead of `HybridSearcher.search`). Function-boundary detection failure for changes deep inside large methods.

6. **`find_dead_code` (0/1):** Regressed from previous run. The `LIKE %name%` reference check produces false negatives when function names appear in indexed documentation/benchmark text.

### Key Recommendations (Priority Order)

1. **Fix `get_context` relevance threshold** — This is the #1 blocker. 10/30 queries (33%) are lost solely because `get_context` returns nothing. Options:
   - Guarantee a minimum number of results (e.g., top-5) regardless of score
   - Lower the relevance floor dramatically
   - Fall back to BM25-only when vector scores are low
   - Add query classification to adjust threshold per query type

2. **Fix `search_regex` permissions** — Two queries cannot be evaluated at all. This has persisted across two runs.

3. **Exclude benchmark reports from the index** — Add `benchmarks/reports/` to a default ignore list. These files cause two distinct problems: (a) index pollution where report prose outranks source code (Q7), and (b) `find_dead_code` false negatives where function names in report text satisfy the `LIKE` reference check (Q26).

4. **Fix `get_diff_context` function boundary detection** — When a diff hunk falls deep inside a large method (e.g., line 554 of a 250-line `search()` method), the tool should attribute it to the enclosing function, not to a different function earlier in the file.

5. **Reduce `get_tests_for` noise** — Filter results to only `test_*.py` files. Don't include fixture definitions, benchmark specs, or conftest helpers as "tests." Apply a per-file cap.

6. **Improve `find_dead_code` reference checking** — Replace `LIKE %name%` with actual import/call graph analysis. The substring match is too permissive when documentation is indexed.

### Verdict

**Arrow's win rate is unchanged at 33% (10/30), but the tool mix has shifted.**

The 10 wins all come from specialized analysis tools: `what_breaks_if_i_change` (2), `trace_dependencies` (2), `resolve_symbol` (2), `file_summary` (2), `project_summary` (1), and `search_structure` enumerate mode (1). These tools provide genuine unique value — capabilities that are impossible or extremely tedious to replicate with traditional tools.

However, Arrow's primary search interface (`get_context`) failed 100% of queries — returning zero results every time. This is unchanged from the previous run and remains the #1 blocker. The `search_regex` permission issue persists. `find_dead_code` regressed due to index pollution from benchmark reports.

**Net assessment:** Arrow is a collection of excellent specialized tools wrapped around a broken primary search tool. The specialized tools should be used aggressively. The search tools should be avoided until `get_context` is fixed.

**Recommended usage strategy:**
- **Always use Arrow for:** `what_breaks_if_i_change`, `trace_dependencies`, `resolve_symbol`, `file_summary`, `project_summary`
- **Use Arrow as supplement for:** `search_structure` (exact names or enumeration), `search_code` (if benchmark reports are excluded from index)
- **Avoid Arrow for:** `get_context` (broken), `search_regex` (broken permissions), broad architectural queries, documentation lookups, config/infra files, needle-in-haystack
