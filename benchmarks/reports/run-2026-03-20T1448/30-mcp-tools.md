# Query 30: What MCP tools does Arrow expose and what does each do?

**Category:** Documentation
**Arrow tool(s) under test:** `get_context`
**Timestamp:** 2026-03-20T14:48

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 14,727 ms |
| Tool calls | 3 (2 Read, 1 Grep) |
| Lines read | ~486 |
| Tokens (est.) | ~1,944 |
| Quality | 5 / 5 |
| Precision | 95% |

**Method:** Read CLAUDE.md (89 lines) and README.md (369 lines), which both contain full tool listings with descriptions. Verified with Grep for `@mcp.tool` across source files (28 matches confirming the README claim).

**Answer quality:** Complete. All 28 MCP tools identified with descriptions, parameters, and categories (Search & Context, Code Analysis, Indexing, Project & Session). Source-verified count.

---

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|--------|-------|
| Wall time | 11,230 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Quality | 1 / 5 |
| Precision | 0% |

**Query:** `"What MCP tools does Arrow expose and what does each do?"`
**Project:** `andreasmyleus/arrow`

**Result:** No results returned. The query returned zero chunks with the suggestion to try broader keywords.

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time | 14,727 ms | 11,230 ms | Arrow (faster but useless) |
| Tokens consumed | ~1,944 | 0 | N/A |
| Quality | 5/5 | 1/5 | **Traditional** |
| Precision | 95% | 0% | **Traditional** |
| Tool calls | 3 | 1 | Arrow |

**Winner: Traditional**

---

## Analysis

This is a documentation-oriented query that asks about a high-level project overview (what tools exist). Arrow's `get_context` failed completely, returning zero results.

**Root cause:** Arrow indexes source code (Python functions, classes, methods) via tree-sitter AST chunking. Documentation files like `README.md` and `CLAUDE.md` are either not indexed, indexed as plain text without semantic structure, or their content does not score above Arrow's relevance thresholds for this query. The query is conceptual ("what tools does Arrow expose") rather than code-focused, so BM25/vector search against code chunks finds no strong match.

**Key insight:** Documentation queries are a known weak spot for code-semantic search tools. The answer lives in Markdown documentation files (README.md, CLAUDE.md), not in code. Traditional file reading is the natural and superior approach for this category. An agent would need to know to read the project's documentation files directly rather than relying on code search.

**Recommendation:** For documentation-category queries, traditional Read of README/CLAUDE.md is the correct strategy. Arrow is designed for code retrieval, not documentation retrieval. This is an expected limitation, not a bug.
