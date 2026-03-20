# Query 30: What MCP tools does Arrow expose and what does each do?

**Category:** Documentation
**Arrow tool tested:** `get_context`

## Round 1 — Traditional (Glob / Grep / Read)

| Metric | Value |
|--------|-------|
| Wall time | 5,699 ms |
| Tool calls | 2 |
| Lines read | ~460 |
| Tokens (est.) | ~1,840 |
| Quality | 5 / 5 |
| Precision | 100% |

**Method:** Read CLAUDE.md and README.md which both contain the full MCP tools listing with descriptions.

**Answer:** Arrow exposes 28 MCP tools across 4 categories: Search & Context (5: get_context, search_code, search_regex, search_structure, resolve_symbol), Code Analysis (6: get_diff_context, what_breaks_if_i_change, get_tests_for, trace_dependencies, find_dead_code, detect_stale_index), Indexing (5: index_codebase, index_git_commit, index_pr, index_github_repo, index_github_content), Project & Session (12: project_summary, file_summary, list_projects, remove_project, export_index, import_index, context_pressure, store_memory, recall_memory, list_memories, delete_memory, tool_analytics). Each tool's purpose is documented in the README table.

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|--------|-------|
| Wall time | 8,516 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Quality | 1 / 5 |
| Precision | 0% |

**Result:** No results returned. Arrow's index contains code chunks (functions, classes, methods) from source files, not documentation content from README.md or CLAUDE.md. The query is purely documentation-oriented — asking about a tool listing that exists only in markdown files, not in code.

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time | 5,699 ms | 8,516 ms | Traditional |
| Tool calls | 2 | 1 | Arrow |
| Tokens used | ~1,840 | 0 | — |
| Quality | 5 | 1 | Traditional |
| Precision | 100% | 0% | Traditional |

## Verdict

**Traditional wins decisively.** This is a documentation query — the answer lives entirely in README.md and CLAUDE.md, which are markdown files that Arrow's code indexer does not chunk or index (it focuses on source code parsed by tree-sitter). Traditional file reading finds the answer immediately in two reads. Arrow returns zero results because the information is not in its index. This represents a known category limitation: documentation-only queries where the answer is in non-code files.
