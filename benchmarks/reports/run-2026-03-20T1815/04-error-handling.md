# Query 04 — Error Handling Patterns

**Query:** "Review error handling patterns across the codebase — where are errors caught, logged, or swallowed?"
**Arrow tool under test:** `get_context`

## Round 1 — Traditional Tools

| Metric | Value |
|---|---|
| Wall-clock ms | 25860 |
| Tool calls | 8 (4 Grep + 1 Glob + 3 Read) |
| Lines read | ~310 |
| Estimated tokens | ~1240 |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Found 50 `try:` blocks across 11 files. Error handling falls into four patterns:

1. **Logged + graceful degradation** (best practice, ~12 occurrences): Catches exception, logs via `logger.exception()` or `logger.warning()`, then falls back. Examples: `embedder.py:130` logs load failure and returns False; `search.py:473` warns on vector search failure and falls back to BM25-only; `indexer.py:67` logs embedding generation failure.

2. **Swallowed silently with `pass`** (~10 occurrences): Catches broad `Exception` and does nothing. Examples: `storage.py:299-300` (migration metadata read); `tools_github.py:115-116` (remote SHA check); `tools_github.py:205-206` (project rename conflict); `vector_store.py:58-59` (key removal); `server.py:290-291` (git root detection); `server.py:1063-1064` (git root fallback).

3. **Returns error JSON to caller** (~5 occurrences): Used in MCP tool functions to surface structured errors. Examples: `tools_github.py:170-174` (gh CLI not found); `tools_github.py:175-179` (clone timeout); `server.py:549-550` (invalid regex); `tools_data.py:217-218` (invalid JSON).

4. **Returns default/empty value** (~8 occurrences): Catches and returns `[]`, `None`, `0`, or `""`. Examples: `storage.py:752-753` returns `[]`; `storage.py:1066-1067` returns `0`; `git_utils.py` consistently returns `None` or `False` on subprocess failures; `chunker.py:521-523` returns `[]` on parse errors.

Notable: `tools_analysis.py` has zero try/except blocks. Only `embedder.py` uses `raise` (RuntimeError for unloaded model). The codebase strongly favors catching over raising.

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall-clock ms | 13812 |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Quality | 1/5 |
| Precision | 0% |

### Findings

`get_context` returned **no results** with the message "No results for: Review error handling patterns across the codebase". The query is a cross-cutting concern (error handling is a pattern spread across many files, not a single function or concept), which does not map well to semantic search over code chunks. The tool's relevance thresholds filtered out everything.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall-clock ms | 25860 | 13812 |
| Tool calls | 8 | 1 |
| Tokens consumed | ~1240 | ~0 |
| Quality | 5/5 | 1/5 |
| Precision | 95% | 0% |

### Verdict

**Traditional wins decisively.** This query is a cross-cutting pattern analysis — "find all try/except blocks and categorize them" — which is fundamentally a regex/grep task. Semantic search cannot answer it because error handling is not a cohesive topic localized in specific chunks; it is a structural pattern distributed across every module. Arrow returned zero results while traditional tools produced a comprehensive inventory of all 50 try/except blocks across 11 files, categorized into four distinct patterns. This is the type of query where grep-based tools have an inherent structural advantage.
