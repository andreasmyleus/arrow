# Benchmark Run: 2026-03-20 (Run 2)

Arrow version: 2de47a1
Codebase: /Users/andreas/arrow (63 files indexed, 828 chunks)
Model: Claude Opus 4.6
Previous run: run-2026-03-20 (ba89121, 58 files)

## Changes Since Last Run

- Added section-aware chunkers for non-code files (TOML, YAML, JSON, Markdown, Dockerfile)
- Improved hybrid ranking: lower RRF k, filename boost, exact-match bonus
- Relevance-first retrieval with precision filtering
- Project scoping fix (auto-detect from cwd)
- Conversation dedup fix
- Doc search support

## Results

| # | Query (short) | Arrow tool(s) | Category | Trad calls | Trad tokens | Arrow tokens | Trad time (s) | Arrow time (s) | Winner | Quality (T/A) |
|---|---------------|---------------|----------|------------|-------------|--------------|---------------|----------------|--------|---------------|
| 1 | Docker setup | get_context | Targeted | 9 | ~364 | 0 | 15.4 | 9.7 | **Traditional** | 5/0 |
| 2 | CI pipeline | get_context | Targeted | 6 | ~204 | 0 | 7.7 | 10.0 | **Traditional** | 5/0 |
| 3 | Hybrid search e2e | get_context | Architecture | 18 | ~4,788 | ~50 | 46.8 | 9.1 | **Traditional** | 5/0 |
| 4 | Error handling | get_context | Architecture | 14 | ~8,500 | ~80 | 47.1 | 6.6 | **Traditional** | 5/0 |
| 5 | Configuration | get_context | Cross-cutting | 8 | ~204 | 0 | 15.1 | 10.6 | **Traditional** | 5/0 |
| 6 | Multi-project | get_context | Cross-cutting | 10 | ~620 | 0 | 30.9 | 6.6 | **Traditional** | 5/0 |
| 7 | Frecency | search_code | Hybrid search | 6 | ~620 | ~3,200 | 10.1 | 7.1 | **Traditional** | 5/4 |
| 8 | RRF scoring | search_code | Hybrid search | 4 | ~5,800 | ~5,200 | 6.8 | 9.8 | **Traditional** | 5/5 |
| 9 | Exception logging | search_regex | Regex | 4 | ~8,500 | ~500 | 16.6 | 0.8 | **Traditional** | 5/1 |
| 10 | Env var reads | search_regex | Regex | 1 | ~4,200 | N/A | 6.8 | N/A | **Traditional** | 5/N/A |
| 11 | estimate_budget | search_structure | Symbol | 2 | ~620 | ~520 | 8.8 | 20.1 | **Traditional** | 5/5 |
| 12 | All classes | search_structure | Symbol | 1 | ~650 | ~3,800 | 6.6 | 32.4 | **Traditional** | 5/2 |
| 13 | Search methods | search_structure | Symbol | 1 | ~650 | ~3,800 | 6.2 | 7.2 | **Arrow** | 3/5 |
| 14 | Storage impact | what_breaks | Impact | 6 | ~260 | ~520 | 18.7 | 7.4 | **Arrow** | 3/5 |
| 15 | Chunker impact | what_breaks | Impact | 7 | ~260 | ~520 | 11.3 | 7.2 | **Arrow** | 4/5 |
| 16 | Storage imports | trace_deps | Dependencies | 2 | ~3,500 | ~3,200 | 8.9 | 10.9 | **Arrow** | 3/5 |
| 17 | Search deps | trace_deps | Dependencies | 2 | ~620 | ~3,200 | 6.4 | 3.8 | **Arrow** | 3/5 |
| 18 | Search tests | get_tests_for | Tests | 4 | ~4,500 | ~8,200 | 19.3 | 6.1 | **Traditional** | 5/4 |
| 19 | Auth tests | get_tests_for | Tests | 4 | ~1,800 | ~4,500 | 13.7 | 9.4 | **Traditional** | 4/3 |
| 20 | Search diff | get_diff_context | Diff | 7 | ~260 | ~520 | 20.1 | 5.4 | **Traditional** | 5/2 |
| 21 | Resolve Storage | resolve_symbol | Cross-repo | 4 | ~260 | ~520 | 10.7 | 7.4 | **Arrow** | 4/5 |
| 22 | Resolve search | resolve_symbol | Cross-repo | 4 | ~650 | ~3,200 | 14.1 | 9.1 | **Arrow** | 3/4 |
| 23 | Server summary | file_summary | File overview | 4 | ~800 | ~350 | 16.2 | 5.3 | **Arrow** | 4/5 |
| 24 | Storage summary | file_summary | File overview | 3 | ~3,500 | ~3,200 | 6.7 | 5.8 | **Arrow** | 4/5 |
| 25 | Project overview | project_summary | Project overview | 10 | ~650 | ~180 | 18.3 | 7.9 | **Traditional** | 5/4 |
| 26 | Dead code | find_dead_code | Dead code | 10 | ~260 | ~520 | 33.4 | 10.6 | **Arrow** | 2/5 |
| 27 | Embedding model | get_context | Needle | 4 | ~2,800 | 0 | 24.2 | 6.1 | **Traditional** | 5/0 |
| 28 | Docker healthcheck | get_context | Needle | 4 | ~2,800 | 0 | 7.7 | 5.5 | **Traditional** | 5/0 |
| 29 | Hash algorithm | get_context | Needle | 5 | ~2,800 | 0 | 9.3 | 3.6 | **Traditional** | 5/1 |
| 30 | MCP tools list | get_context | Documentation | 5 | ~3,500 | 0 | 10.5 | 9.4 | **Traditional** | 5/0 |

## Per-tool Summary

| Arrow tool | Queries tested | Wins | Losses | Avg quality (T/A) | Best use case |
|------------|---------------|------|--------|-------------------|---------------|
| get_context | 10 (Q1-6, 27-30) | 0 | 10 | 5.0/0.1 | *None in this benchmark* |
| search_code | 2 (Q7-8) | 0 | 2 | 5.0/4.5 | Ranked keyword+semantic search |
| search_regex | 2 (Q9-10) | 0 | 2 | 5.0/0.5 | Single-line pattern matching |
| search_structure | 3 (Q11-13) | 1 | 2 | 4.3/4.0 | Exact symbol lookup (Q13) |
| what_breaks_if_i_change | 2 (Q14-15) | 2 | 0 | 3.5/5.0 | Impact analysis — always use |
| trace_dependencies | 2 (Q16-17) | 2 | 0 | 3.0/5.0 | Import graph — always use |
| get_tests_for | 2 (Q18-19) | 0 | 2 | 4.5/3.5 | Function-specific test lookup |
| get_diff_context | 1 (Q20) | 0 | 1 | 5.0/2.0 | Active development (needs uncommitted changes) |
| resolve_symbol | 2 (Q21-22) | 2 | 0 | 3.5/4.5 | Cross-repo symbol resolution — always use |
| file_summary | 2 (Q23-24) | 2 | 0 | 4.0/5.0 | File structure overview — always use |
| project_summary | 1 (Q25) | 0 | 1 | 5.0/4.0 | Quick project stats (supplement with reads) |
| find_dead_code | 1 (Q26) | 1 | 0 | 2.0/5.0 | Dead code detection — always use |

## Totals

| Metric | Traditional | Arrow |
|--------|-------------|-------|
| Total tool calls | 169 | 56 |
| Total content tokens | ~64,940 | ~45,780 |
| Total wall time | 474.4s | 244.4s* |
| Avg answer quality | 4.40 | 2.76 |
| Queries won | **20** | **10** |
| Zero-result queries | 0 | 11 |

\* Arrow faster in total wall time but largely because zero-result queries return instantly

## Comparison With Previous Run (run-2026-03-20)

| Metric | Previous Run | This Run | Change |
|--------|-------------|----------|--------|
| Arrow wins | 3/20 | 10/30 | +7 wins (33% win rate, up from 15%) |
| Arrow zero-result queries | 4/20 | 11/30 | Worse ratio (37% vs 20%) |
| Arrow avg quality | 2.85 | 2.76 | Slightly worse |
| Cross-project contamination | Frequent | None observed | Fixed |
| Conversation dedup issues | Yes | N/A (independent agents) | Not tested |
| Non-code file indexing | Missing | Files indexed but not searchable | Partially fixed |

## Analysis

### The Critical Problem: `get_context` Returns Zero Results (11/30 queries)

The #1 issue is that `get_context` returned **zero results** for 11 of 30 queries. This is catastrophically worse than the previous run (4/20 zero-result queries). The relevance-first filtering improvement has overcorrected — the threshold is now so aggressive that most queries are completely rejected.

Affected query types:
- **All 6 targeted/architectural get_context queries** (Q1-6): 0/5 quality
- **All 3 needle-in-haystack queries** (Q27-29): 0/5 quality
- **Documentation query** (Q30): 0/5 quality
- **Docker healthcheck** (Q28): 0/5 quality

The previous run's `get_context` returned too much irrelevant content (18K-30K tokens). The fix swung too far — now it returns nothing. The ideal is somewhere in between.

### Where Arrow Excels (10 wins, 5 categories)

Arrow's **specialized analysis tools** are genuinely excellent:

1. **Impact analysis** (`what_breaks_if_i_change`): 2/2 wins, avg 5.0 quality. Found 30 callers + 22 tests + risk rating where Traditional found only 9 callers. No viable traditional alternative.

2. **Dependency tracing** (`trace_dependencies`): 2/2 wins, avg 5.0 quality. Full bidirectional + transitive import graphs. Traditional can only do forward imports.

3. **Symbol resolution** (`resolve_symbol`): 2/2 wins, avg 4.5 quality. Cross-repo lookup with zero noise. Traditional requires knowing repo locations.

4. **File summaries** (`file_summary`): 2/2 wins, avg 5.0 quality. Structured JSON with functions, classes, token counts. 3x faster than reading the file.

5. **Dead code detection** (`find_dead_code`): 1/1 win, 5.0 quality. Qualitative capability gap — practically impossible with traditional tools.

### Where Arrow Fails

1. **`get_context` is broken**: 0/10 wins. The relevance threshold rejects everything. This tool is Arrow's primary interface and it's currently non-functional for most query types.

2. **Non-code files not searchable**: Dockerfile, CI config (.github/), docker-compose.yml chunks exist in the index but don't surface in search results (Q1, Q2, Q28).

3. **`search_regex` lacks multiline**: Cross-line patterns like except→log fail (Q9). Traditional Grep with -A context handles this naturally.

4. **`search_structure` lacks enumeration**: No wildcard/list-all mode. Finding "all classes" required 27 API calls and still only found 51% (Q12).

5. **`get_tests_for` has recall gaps**: Function-name-based matching misses test files that don't follow naming conventions (Q18-19).

### Key Recommendations (Priority Order)

1. **Fix `get_context` relevance threshold** — this is the most impactful change. The threshold should:
   - Use a much lower floor (or make it configurable)
   - Return a minimum number of results (e.g., top-5) regardless of score
   - Fall back to BM25-only results when vector similarity is low
   - Scale the threshold based on query type (broad vs specific)

2. **Make non-code file search work** — Dockerfile, YAML, TOML, CI configs are indexed (63 files) but never returned in search results. The embedding model may not encode these file types well.

3. **Add multiline regex support** to `search_regex` — or at least a `context_lines` behavior that groups adjacent matches.

4. **Add `search_structure` list/wildcard mode** — `kind="class"` with no symbol should return all classes.

5. **Add `ref` parameter to `get_diff_context`** — allow analyzing historical commits, not just uncommitted changes.

6. **Improve `get_tests_for` recall** — supplement name-based matching with import graph analysis and content search.

### Verdict

**Arrow's specialized tools are excellent; its primary search tool is broken.**

The 10 Arrow wins all came from purpose-built analysis tools (impact, dependencies, symbols, summaries, dead code) that provide unique value impossible to replicate with traditional tools. These should be used whenever applicable.

However, `get_context` — Arrow's flagship tool and the one most queries route through — returned zero results for 11/30 queries, making it actively harmful compared to Glob/Grep/Read. Until the relevance threshold is fixed, `get_context` should not be the default recommendation.

**Recommended usage strategy:**
- **Always use Arrow for:** `what_breaks_if_i_change`, `trace_dependencies`, `resolve_symbol`, `file_summary`, `find_dead_code`
- **Use Arrow as supplement for:** `search_structure` (exact names), `search_code` (ranked results), `project_summary` (quick stats)
- **Avoid Arrow for:** `get_context` (broken threshold), broad architectural queries, documentation lookups, config/infra files, needle-in-haystack
