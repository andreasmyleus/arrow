# Query 30: What MCP tools does Arrow expose and what does each do?

**Category:** Documentation
**Timestamp:** 2026-03-20T15:30

## Round 1 — Traditional Tools

| Metric | Value |
|--------|-------|
| Start | 1774007912039 |
| End | 1774007922493 |
| Duration | 10454 ms |
| Tool calls | 5 (3 parallel Glob/Read, 1 Grep, 1 timestamp) |
| Quality | 5/5 |
| Precision | 100% |

**Approach:** Read CLAUDE.md which contains the full tool table (28 tools across 6 categories), then cross-verified with Grep for `@mcp.tool()` decorators across all source files to confirm every documented tool is actually registered (28 decorators found matching the 28 documented tools).

**Answer found:** Arrow exposes 28 MCP tools organized in 6 categories:

- **Search & Retrieval (4):** get_context, search_code, search_regex, search_structure
- **Analysis & Impact (7):** get_diff_context, what_breaks_if_i_change, trace_dependencies, resolve_symbol, get_tests_for, find_dead_code, detect_stale_index
- **Project Management (5):** index_codebase, list_projects, project_summary, file_summary, remove_project
- **GitHub & Remote (4):** index_github_repo, index_github_content, index_git_commit, index_pr
- **Portability (2):** export_index, import_index
- **Session & Memory (6):** context_pressure, tool_analytics, store_memory, recall_memory, list_memories, delete_memory

Each tool's description was available in CLAUDE.md with parameters and one-line summaries.

## Round 2 — Arrow MCP

| Metric | Value |
|--------|-------|
| Start | 1774007924930 |
| End | 1774007934353 |
| Duration | 9423 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

**Approach:** Single `get_context` call with the query.

**Result:** No results returned. The query is documentation-oriented and the answer lives in CLAUDE.md (a Markdown file). Arrow's relevance thresholds filtered out all chunks — likely because the tool table in CLAUDE.md is structured as bullet-point documentation rather than code, and the natural-language query didn't match code chunks well enough to pass the relevance cutoff.

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 10454 ms | 9423 ms |
| Tool calls | 5 | 1 |
| Quality | 5/5 | 0/5 |
| Precision | 100% | 0% |
| Tokens in | ~3500 | ~200 |
| Tokens out | ~3500 | ~50 |

**Winner:** Traditional

**Analysis:** This is a pure documentation query. The answer is a curated tool table in CLAUDE.md, not something embedded in code. Arrow's code-focused search and relevance filtering returned zero results. Traditional tools excel here — a single Read of CLAUDE.md gives the complete answer, and Grep verification confirms accuracy. Arrow would need to either index Markdown documentation more aggressively or have lower relevance thresholds for doc-style queries to handle this case.

**Category pattern:** Documentation queries that ask about project-level facts (tool lists, architecture, configuration) are poorly served by code search. The information is typically in README/CLAUDE.md files that are better accessed directly.
