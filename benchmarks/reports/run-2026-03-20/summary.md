# Benchmark Run: 2026-03-20

Arrow version: ba89121
Codebase: /Users/andreas/arrow (58 files indexed)
Model: Claude Opus 4.6

## Results

| # | Query (short) | Category | Trad calls | Trad tokens | Arrow tokens | Trad time (s) | Arrow time (s) | Winner | Quality (T/A) |
|---|---------------|----------|------------|-------------|--------------|---------------|----------------|--------|---------------|
| 1 | Docker setup | Targeted | 4 | ~240 | ~30,000 | 9.3 | 6.9 | **Traditional** | 5/3 |
| 2 | CI pipeline | Targeted | 2 | ~200 | ~3,075 | 9.2 | 7.1 | **Traditional** | 5/0 |
| 3 | pyproject.toml | Targeted | 1 | ~200 | 0 | 6.4 | 13.0 | **Traditional** | 5/0 |
| 4 | Hybrid search e2e | Architecture | 6 | ~1,120 | ~21,282 | 20.1 | 11.8 | **Tie** | 5/3 |
| 5 | Error handling | Architecture | 1 | ~360 | ~18,077 | 6.9 | 7.1 | **Traditional** | 4/4 |
| 6 | Incremental indexing | Architecture | 1 | ~400 | 0 | 8.6 | 6.9 | **Traditional** | 5/0 |
| 7 | Data model / SQLite | Architecture | 1 | ~800 | ~25,687 | 6.5 | 7.8 | **Traditional** | 5/3 |
| 8 | estimate_budget | Symbol | 2 | ~100 | ~21,736 | 9.9 | 6.6 | **Traditional** | 5/3 |
| 9 | Frecency | Symbol | 2 | ~480 | ~5,997 | 9.4 | 7.9 | **Traditional** | 5/4 |
| 10 | RRF scoring | Symbol | 0* | ~60 | ~2,804 | 6.5 | 8.0 | **Traditional** | 5/3 |
| 11 | Storage impact | Impact | 3 | ~80 | structured | 11.8 | 7.1 | **Arrow** | 4/5 |
| 12 | Search tests | Impact | 1 | ~320 | ~5,997 | 7.0 | 7.9 | **Tie** | 5/5 |
| 13 | Storage imports | Impact | 0* | ~40 | structured | 4.4 | 9.4 | **Arrow** | 4/5 |
| 14 | Configuration | Cross-cutting | 2 | ~800 | ~8,974 | 11.6 | 9.7 | **Tie** | 5/4 |
| 15 | Test infrastructure | Cross-cutting | 1 | ~490 | ~2,220 | 6.7 | 7.9 | **Traditional** | 5/4 |
| 16 | Multi-project | Cross-cutting | 1 | ~40 | ~5,810 | 7.6 | 8.8 | **Arrow** | 3/5 |
| 17 | Embedding model | Needle | 1 | ~200 | ~12,919 | 7.4 | 8.8 | **Traditional** | 5/3 |
| 18 | Docker healthcheck | Needle | 0* | ~4 | ~307 | 4.7 | 7.8 | **Traditional** | 5/0 |
| 19 | Hash algorithm | Needle | 1 | ~100 | ~3,362 | 7.6 | 8.2 | **Traditional** | 5/4 |
| 20 | MCP tools list | Documentation | 1 | ~160 | ~6,495 | 7.8 | 10.9 | **Traditional** | 5/2 |

\* Reused results from earlier queries in same session (traditional's advantage from caching context)

## Totals

| Metric | Traditional | Arrow |
|--------|-------------|-------|
| Total tool calls | 31 | 23 |
| Total content tokens | ~6,194 | ~175,742 |
| Total wall time | 169.4s | 169.2s |
| Avg answer quality | 4.85 | 2.85 |
| Queries won | **13** | 3 |
| Ties | 3 | 3 |
| Avg precision | ~89% | ~27% |

## Analysis

### Where Traditional Won (13/20)

Traditional tools dominated because:

1. **Targeted lookups (UC1-3):** Glob+Read directly opens known files. Arrow returned wrong project (pydantic), no results (toml not indexed), or 30K tokens of noise.

2. **Symbol lookups (UC8-10):** `grep def function_name` + Read targeted section is surgically precise. Arrow returned the right function buried in 20K+ tokens of unrelated code.

3. **Needle-in-haystack (UC17-19):** Grep finds the exact line. Arrow's conversation-aware dedup actually *hurt* it — Dockerfile was excluded in UC18 because it was "already sent" in UC1.

4. **Documentation (UC20):** README grep is instant and precise. Arrow returned source code instead of the documentation table.

### Where Arrow Won (3/20)

Arrow excelled at **impact analysis** (UC11, 13, 16):

- `what_breaks_if_i_change` provided structured caller/test/dependent analysis that would require many grep+read cycles
- `trace_dependencies` gave a full import graph with transitive importers
- Multi-project questions benefited from Arrow's cross-file knowledge

### Key Issues Identified

1. **Token budget explosion:** `get_context` with auto-budget returned 18K-30K tokens for simple questions. The `estimate_budget` heuristic seems miscalibrated — it doesn't account for already-indexed projects from other repos (pydantic).

2. **Cross-project contamination:** UC2 returned pydantic pipeline code for "CI pipeline". The word "pipeline" matched pydantic's `_Pipeline` class. Project scoping (`project=`) fixes this but requires knowing the project name first (extra call).

3. **Conversation dedup backfires:** UC17 and UC18 missed key information because chunks were marked as "already sent" from earlier queries. In a benchmark setting where each query should be independent, this is actively harmful.

4. **Non-code files not indexed:** pyproject.toml returned 0 results. Config/build files are important for many questions.

5. **Precision is consistently low:** Even when Arrow found the right answer, it was embedded in 50x more irrelevant content, increasing token cost and reducing answer quality.

### Recommendations

1. **Fix project scoping default:** When cwd is inside a project, default to that project instead of searching all indexed repos
2. **Reduce auto-budget:** The heuristic over-estimates — 500-2000 tokens is enough for most targeted queries
3. **Index non-code files:** toml, yaml, Dockerfile, markdown should be searchable
4. **Add session reset between independent queries** or make dedup optional
5. **Use specialized tools:** `what_breaks_if_i_change`, `trace_dependencies`, `get_tests_for` are genuinely valuable — `get_context` should be the fallback, not the primary tool

### Verdict

**Traditional tools (Glob/Grep/Read) are superior for the vast majority of code exploration tasks** in this codebase. They're precise, predictable, and low-token-cost. Arrow's `get_context` suffers from over-retrieval, cross-project contamination, and conversation dedup issues.

However, Arrow's **specialized analysis tools** (impact analysis, dependency tracing, test discovery) provide unique value that traditional tools cannot match. The recommendation is to use Arrow's analysis tools selectively while relying on traditional tools for search and retrieval.
