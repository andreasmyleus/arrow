# Query 20: "What functions changed in search.py and who calls them?"

Category: Diff analysis
Arrow tool(s) under test: get_diff_context

## Round 1 — Traditional

**Timestamps:** start=1774009942457 end=1774009968810
**Wall time:** 26353ms
**Tool calls:** 8 (Bash x4, Grep x3, Read x0, Glob x0)
**Tokens from content:** ~400 (diff output ~40 lines + grep results ~60 lines = ~100 lines x ~4 tokens)
**Answer quality:** 5
**Precision:** 95%

### Answer

The most recent commit touching search.py is `340e987` ("Boost search results when query matches filename or path for all file types"). The change is within `HybridSearcher.search()` (line 404-654):

**What changed:** The `_filename_match_boost()` call was moved earlier in the scoring logic — computed before the non-code penalty check instead of after. A new `elif name_boost > 1.0: pass` branch was added so that when a filename matches the query, the non-code penalty (0.3x multiplier) is skipped entirely.

**Functions modified:**
- `HybridSearcher.search` — the main search method (lines 404-654)
- `_filename_match_boost` — not modified itself, but its call site was relocated

**Callers of `HybridSearcher.search`:**
- `src/arrow/server.py:491` — `search_code` MCP tool handler
- `src/arrow/cli.py:192` — CLI `search` command
- `src/arrow/search.py:720` — internal `get_context_results` method

**Callers of `_filename_match_boost`:**
- `src/arrow/search.py:561` — only called within `HybridSearcher.search`

The previous commit `e0f2200` also modified search.py, changing `_MIN_SCORE_RATIO`, `_SCORE_DROP_RATIO`, `_MIN_RESULTS_FLOOR` constants, expanding `_CONFIG_QUERY_TERMS`, adding `"dockerfile"` to `_NON_CODE_LANGS`, and updating `_extract_query_concepts`.

### Files read
- git diff output for 340e987 (~40 lines)
- git diff output for e0f2200 (~60 lines)
- grep results for callers (~30 lines)

## Round 2 — Arrow

**Timestamps:** start=1774009971611 end=1774009985431
**Wall time:** 13820ms
**Tool calls:** 1 (get_diff_context x1)
**Tokens from content:** ~1200 (estimated from response size)
**Chunks returned:** 1 changed function + 10 callers + 13 dependent files
**Answer quality:** 3
**Precision:** 60%

### Answer

`get_diff_context` with `ref=340e987` identified `_is_doc_path` as the changed function rather than the actual modified function `HybridSearcher.search`. The diff in commit 340e987 occurs within the `search` method body (lines 554-575), but the tool attributed the change to `_is_doc_path` (lines 66-94), which is a different function earlier in the file that was NOT modified in this commit.

It did correctly identify 10 callers of `_is_doc_path` (9 tests + `search` method) and 13 dependent files, but since the wrong function was identified as changed, the caller list doesn't answer the actual question.

The tool missed that `HybridSearcher.search` was the changed function, and therefore didn't surface its callers (server.py, cli.py, internal get_context_results).

### Files read
- (none — single tool call)

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 26353ms | 13820ms |
| Tool calls | 8 | 1 |
| Tokens consumed | ~400 | ~1200 |
| Quality | 5 | 3 |
| Precision | 95% | 60% |

### Notes

Arrow was faster (1 tool call vs 8) and simpler to use, but produced an incorrect result — it attributed the change to the wrong function (`_is_doc_path` instead of `HybridSearcher.search`). This appears to be a function-boundary detection issue: the diff hunks at lines 554-575 are deep inside the `search` method, but the tool mapped them to a different function. The caller analysis was accurate for the (wrong) function it identified.

The traditional approach required more manual work (running git log, git diff, multiple grep searches) but correctly identified the changed function and its callers. For diff analysis, accuracy of function identification is critical — getting the wrong function makes the entire caller analysis misleading.

**Winner: Traditional** — despite being slower, it produced the correct answer. Arrow's speed advantage is negated by the misidentified function.
