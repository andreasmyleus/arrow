# Query 23: File Overview — server.py Summary

**Query:** "Give me an overview of server.py — what functions does it have, how big is it?"
**Category:** File overview
**Arrow tool tested:** `file_summary`

## Round 1 — Traditional Tools

| Metric | Value |
|--------|-------|
| Wall time | 21,630 ms |
| Tool calls | 8 (1 wc + 6 Read + 1 Bash) |
| Tokens consumed (est.) | ~4,676 (1169 lines x ~4 tokens/line) |
| Quality | 5/5 |
| Precision | 95% |

**Method:** Used `wc -l` to get line count (1169), then read the entire file in 6 sequential Read calls (200 lines each) to identify all functions, classes, imports, and structure.

**Findings:** 1169 lines, 30 functions (5 singleton getters, 7 internal helpers, 6 MCP tool functions, 5 regex search helpers, 2 formatting helpers, 3 startup/entry-point functions, plus nested `on_change` and `_warm`). No classes defined in the file. Imports from 13+ modules.

## Round 2 — Arrow (`file_summary`)

| Metric | Value |
|--------|-------|
| Wall time | 16,033 ms |
| Tool calls | 1 |
| Tokens returned (est.) | ~800 (structured JSON summary) |
| Quality | 5/5 |
| Precision | 92% |

**Findings:** Returned structured JSON with all 30 functions, line ranges, per-function token counts, total tokens (8201), 30 chunks, language (python), imports list, and confirmation of no classes. Import parsing had minor noise (e.g. `"( # noqa: F401"` appearing as an import).

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time (ms) | 21,630 | 16,033 | Arrow (1.3x faster) |
| Tool calls | 8 | 1 | Arrow (8x fewer) |
| Tokens consumed | ~4,676 | ~800 | Arrow (5.8x fewer) |
| Quality (1-5) | 5 | 5 | Tie |
| Precision (%) | 95% | 92% | Traditional (slight edge) |

## Analysis

Arrow's `file_summary` is well-suited for this exact use case — getting a structural overview of a file without reading the entire contents. It returned all 30 functions with line ranges and token counts in a single call, consuming ~5.8x fewer tokens than reading the full 1169-line file.

The traditional approach has a slight precision edge because reading the raw file lets you see the full context (constants, module-level variables, section comments, decorator patterns). Arrow's import parsing had minor noise with noqa comments being captured as imports.

**Verdict:** Arrow wins on efficiency. For "what functions does this file have and how big is it?" the structured summary is ideal — compact, complete, and avoids flooding context with 1169 lines of source code.
