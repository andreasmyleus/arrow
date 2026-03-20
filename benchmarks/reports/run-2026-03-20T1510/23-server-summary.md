# Query 23: Server.py Overview

**Query:** "Give me an overview of server.py — what functions does it have, how big is it?"
**Category:** file_summary — File overview
**Arrow tool under test:** `file_summary`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 22,192 ms |
| Tool calls | 7 (1 Bash wc, 6 Read calls to cover 1178 lines) |
| Estimated tokens sent | ~14,000 (full file content across 6 reads) |
| Estimated tokens received | ~12,000 (raw file lines) |
| Quality | 5/5 — full file content read, complete function list obtainable |
| Precision | 100% — every line read directly from disk |

**Process:** Ran `wc -l` to get line count (1178 lines), then read the entire file in 6 sequential Read calls (200 lines each). Had to manually scan and mentally catalog all functions, classes, imports, and module-level constants.

**Summary from traditional read:**
- 1178 lines, Python
- 30 functions total
- 5 MCP tool functions: `index_codebase`, `list_projects`, `project_summary`, `search_code`, `search_regex`, `get_context`, `search_structure`
- Internal helpers: `_get_storage`, `_get_vector_store`, `_get_embedder`, `_get_indexer`, `_get_searcher`, `_get_project_lock`, `_start_watcher`, `_stop_watcher`, `_start_all_watchers`, `_detect_project_from_cwd`, `_resolve_project_id`, `_check_project_id`, `_ensure_indexed`, `_record_chunk_sent`, `_fmt_chunk`, `_fmt_chunks`, `_search_regex_on_disk`, `_search_regex_in_chunks`, `_format_regex_results`, `_auto_warm_cwd`, `_warm`, `main`, `on_change`
- No classes defined in this file
- Imports from 10+ internal modules and standard library
- Registers tools from `tools_analysis`, `tools_github`, `tools_data` submodules

---

## Round 2 — Arrow (`file_summary`)

| Metric | Value |
|--------|-------|
| Wall time | 11,102 ms |
| Tool calls | 1 |
| Estimated tokens sent | ~100 (tool parameters) |
| Estimated tokens received | ~2,500 (structured JSON summary) |
| Quality | 5/5 — complete function list with line ranges and token counts |
| Precision | 97% — all functions listed correctly; import list has some parsing artifacts (e.g., `"( # noqa: F401"` as an import name) |

**Results from Arrow:**
- 8,255 total tokens across 30 chunks
- 30 functions listed with exact line ranges and per-function token counts
- 0 classes
- Full import list (with minor parsing artifacts on noqa-annotated imports)
- Largest functions: `get_context` (1001 tokens, lines 801-911), `search_structure` (962 tokens, lines 915-1052), `search_regex` (652 tokens, lines 523-598)

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time | 22,192 ms | 11,102 ms | Arrow (2.0x faster) |
| Tool calls | 7 | 1 | Arrow (7x fewer) |
| Tokens consumed | ~26,000 | ~2,600 | Arrow (10x fewer) |
| Quality | 5/5 | 5/5 | Tie |
| Precision | 100% | 97% | Traditional (minor) |
| Structured output | No (raw text) | Yes (JSON with line ranges, token counts) | Arrow |

**Token savings: ~23,400 tokens (90% reduction)**

## Verdict

Arrow delivers a significantly better experience for file overview queries. The traditional approach required reading the entire 1178-line file across 6 sequential tool calls and then manually parsing the structure, consuming ~26K tokens. Arrow returned a structured JSON summary in a single call with ~2.6K tokens, including per-function token counts and line ranges that the traditional approach cannot provide without additional processing.

The only minor drawback is some import parsing artifacts on lines with `noqa` comments, which does not affect the core value of the summary. For the "give me an overview" use case, Arrow's `file_summary` is clearly the right tool.
