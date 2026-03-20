# Query 23: Server.py Overview

**Category:** file_summary — Per-file breakdown
**Query:** "Give me an overview of server.py — what functions does it have, how big is it?"

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Start | 1774007890576 |
| End | 1774007906756 |
| Duration | 16,180 ms |
| Tool calls | 4 (wc -l, Grep defs, Read top, Read mid-section) |
| Lines read | ~200 lines |
| Tokens (est.) | ~800 (output lines x4) |
| Quality | 4/5 |
| Precision | 85% |

**Method:** Used `wc -l` to get file size (1,123 lines), `Grep` for all `def`/`class` lines (found 28 top-level defs), and `Read` for imports and function bodies. Required multiple reads to piece together the structure. Missing: per-function token counts, inner function (`on_change`, `_warm`), and complete imports list.

**Answer produced:**
- 1,123 lines, 28 top-level functions, 0 classes
- Key MCP tools: `index_codebase`, `list_projects`, `project_summary`, `search_code`, `search_regex`, `get_context`, `search_structure`
- Helper/internal: `_get_storage`, `_get_vector_store`, `_get_embedder`, `_get_indexer`, `_get_searcher`, `_get_project_lock`, `_start_watcher`, `_stop_watcher`, `_start_all_watchers`, `_detect_project_from_cwd`, `_resolve_project_id`, `_check_project_id`, `_ensure_indexed`, `_record_chunk_sent`, `_fmt_chunk`, `_fmt_chunks`, `_search_regex_on_disk`, `_search_regex_in_chunks`, `_format_regex_results`, `_auto_warm_cwd`, `main`

## Round 2 — Arrow (file_summary)

| Metric | Value |
|---|---|
| Start | 1774007911976 |
| End | 1774007917308 |
| Duration | 5,332 ms |
| Tool calls | 1 |
| Lines read | 0 (no file reads) |
| Tokens (est.) | ~350 (structured JSON response) |
| Quality | 5/5 |
| Precision | 98% |

**Method:** Single `file_summary` call returned complete structured JSON with all 30 functions (including nested `on_change` and `_warm`), line ranges, per-function token counts, imports list, total tokens (7,749), and chunk count (30).

**Answer produced:**
- 1,123 lines, 7,749 tokens, 30 chunks
- 30 functions with exact line ranges and token sizes
- Largest functions: `get_context` (1,001 tokens, lines 767-877), `search_structure` (797 tokens, lines 881-997), `search_regex` (562 tokens, lines 514-584)
- Complete imports list including internal module imports
- 0 classes

## Comparison

| Metric | Traditional | Arrow | Winner |
|---|---|---|---|
| Duration | 16,180 ms | 5,332 ms | Arrow (3.0x faster) |
| Tool calls | 4 | 1 | Arrow |
| Completeness | Missed 2 nested functions, no token counts | All 30 functions with tokens + line ranges | Arrow |
| Precision | 85% | 98% | Arrow |
| Quality | 4/5 | 5/5 | Arrow |
| Tokens consumed | ~800 | ~350 | Arrow (2.3x fewer) |

## Verdict

**Arrow wins decisively.** The `file_summary` tool is purpose-built for this query type. It returns a structured, complete breakdown in a single call — including per-function token counts and line ranges that would require reading the entire file to compute traditionally. Traditional tools needed 4 calls and still missed nested functions and token metrics.
