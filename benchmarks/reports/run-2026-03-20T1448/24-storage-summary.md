# Query 24: "What's in storage.py — structure, classes, methods?"

**Category:** File overview
**Arrow tool(s) under test:** `file_summary`
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 13,247 ms |
| Tool calls | 5 (Glob x1, Grep x2, Read x1, Bash/wc x1) |
| Tokens read | ~536 (134 lines of grep output + file head) |
| Quality | 5/5 |
| Precision | 98% |

### Findings

- **File:** 1,458 lines, Python, SQLite WAL storage layer
- **6 classes** (dataclasses + main class):
  - `ProjectRecord` (L16-28) — project metadata
  - `FileRecord` (L32-40) — indexed file record
  - `ChunkRecord` (L44-55) — code chunk with zstd-compressed content
  - `SymbolRecord` (L59-64) — AST symbol entry
  - `ImportRecord` (L68-70) — file-level import edge
  - `Storage` (L240+) — main class, all DB operations
- **57 methods** on `Storage`, covering: schema init, migrations (v1-v4), project CRUD, file CRUD, chunk operations, FTS5 search, regex search, symbol search, caller/dependency analysis, frecency tracking, tool analytics, session tracking, memory store/recall, staleness detection, dead code finder
- Imports: sqlite3, time, dataclasses, pathlib, typing

### Process

1. Glob confirmed file exists.
2. Two parallel Grep calls extracted all `class` definitions (6 hits) and all `def` definitions (57 hits) with line numbers.
3. Read first 70 lines to get dataclass field details and imports.
4. `wc -l` confirmed total line count.

This gave a complete structural picture but required assembling information from multiple tool outputs.

---

## Round 2 — Arrow (`file_summary`)

| Metric | Value |
|--------|-------|
| Wall time | 7,320 ms |
| Tool calls | 1 |
| Chunks returned | 63 |
| Tokens in response | ~3,200 (structured JSON) |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Single call returned a structured JSON summary containing:
- **Language:** Python, **total tokens:** 10,977 across 63 chunks
- **6 classes** with line ranges and token counts
- **57 functions/methods** each with name, line range, and token count
- **11 imports** listed individually
- Token counts per function enable quick identification of complexity hotspots (e.g., `_migrate_v1_to_v2` at 762 tokens, `find_dead_code` at 421 tokens, `recall_memory` at 382 tokens)

### Minor inaccuracies

- `ImportRecord` reported as spanning lines 68-237 with 1,239 tokens — this is incorrect; `ImportRecord` is a 3-line dataclass (L68-70). The chunk likely merged it with standalone code that follows.
- `Storage` class reported as lines 240-241 with 21 tokens — this is just the class definition line, not the full class. All methods are listed separately as top-level functions rather than as methods of `Storage`.
- These are cosmetic issues; all methods and classes are still present and discoverable.

---

## Comparison

| Dimension | Traditional | Arrow | Winner |
|-----------|------------|-------|--------|
| Wall time | 13,247 ms | 7,320 ms | **Arrow** (1.8x faster) |
| Tool calls | 5 | 1 | **Arrow** (5x fewer) |
| Completeness | All classes, all methods, field details, imports | All classes, all methods, token counts, imports | **Arrow** (token counts add value) |
| Accuracy | Correct line numbers, correct class boundaries | Minor boundary issues on ImportRecord/Storage | **Traditional** |
| Effort to interpret | Must assemble from multiple outputs | Single structured JSON | **Arrow** |
| Token cost to LLM | ~536 tokens read | ~3,200 tokens in response | **Traditional** (6x less) |

---

## Verdict

**Arrow wins overall.** The `file_summary` tool delivers a complete structural overview of a 1,458-line file in a single call, including per-function token counts that traditional tools cannot easily provide. The 1.8x speed improvement and 5x reduction in tool calls make it the clear choice for file overview queries. The minor inaccuracies in chunk boundary reporting (ImportRecord spanning to line 237, Storage showing only 2 lines) do not materially affect usability since all 57 methods and 6 classes are correctly enumerated. The main trade-off is that the Arrow response is larger (~3,200 tokens vs ~536), but this is structured JSON that is easy for an LLM to parse and provides richer information (token counts per function).

**Recommendation:** Use `file_summary` as the default tool for "what's in this file" queries. Fall back to Grep for `def`/`class` when you need exact class boundaries or when token budget is very tight.
