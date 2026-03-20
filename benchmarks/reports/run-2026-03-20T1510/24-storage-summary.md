# Query 24: What's in storage.py — structure, classes, methods?

**Category:** file_summary — File overview
**Arrow tool under test:** `file_summary`
**Timestamp:** 2026-03-20T15:10

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 26,393 ms |
| Tool calls | 8 (8x Read across chunks of the 1,472-line file) |
| Tokens sent (est.) | ~12,000 (full file content read in 8 passes) |
| Tokens received (est.) | ~500 (summary would go here) |
| Quality | 5/5 |
| Precision | 100% |

**Process:** Read the entire 1,472-line file in 8 sequential Read calls (150-200 lines each) to capture every class, method, dataclass, and the full schema SQL. Obtained complete picture of the file structure.

**Summary from traditional read:**
- **Dataclasses (5):** `ProjectRecord`, `FileRecord`, `ChunkRecord`, `SymbolRecord`, `ImportRecord`
- **Main class:** `Storage` — SQLite-backed storage with WAL mode, FTS5, multi-project support
- **Schema:** 9 tables (projects, files, chunks, chunks_fts, symbols, imports, file_access, tool_analytics, session_chunks, memories, memories_fts), schema version 4, 3 migration paths (v1->v2, v2->v3, v3->v4)
- **Methods (57):** Organized into sections: project ops (create/get/update/delete/list), file ops (get/upsert/delete/getAll), chunk ops (insert/batch/get/search_fts/search_regex), symbol ops (insert/search/enumerate), stats, caller analysis, test files, import tracing, cross-repo resolution, frecency tracking, tool analytics, session context, long-term memory (store/recall/list/delete), stale index detection, dead code detection
- **Imports:** sqlite3, time, dataclasses, pathlib, typing, re (lazy)
- **Total lines:** 1,472

---

## Round 2 — Arrow (`file_summary`)

| Metric | Value |
|---|---|
| Wall time | 8,918 ms |
| Tool calls | 1 |
| Tokens sent (est.) | ~50 (tool parameters) |
| Tokens received (est.) | ~3,500 (structured JSON response) |
| Quality | 4/5 |
| Precision | 90% |

**Results:** Returned structured JSON with:
- **Language:** Python
- **Total tokens:** 11,094 across 63 chunks
- **Functions:** 57 methods listed with name, line range, and token count
- **Classes:** 6 listed (ProjectRecord, FileRecord, ChunkRecord, SymbolRecord, ImportRecord, Storage)
- **Imports:** 11 import names listed
- **Other:** empty

**Minor issues:**
- `ImportRecord` is listed as spanning lines 68-237 (1,239 tokens), which actually covers the `SCHEMA_V2_SQL` constant plus the dataclass itself. The chunker grouped the SQL schema constant with the preceding dataclass, inflating its apparent size. Not incorrect per se (the SQL is module-level code between two class-level constructs), but misleading.
- `Storage` class body shows lines 240-241 with only 21 tokens — it only captured the class declaration line + docstring, not the class as a whole. The methods are listed individually, which is correct behavior for the chunker but means you don't see that all 57 methods belong to `Storage`.
- No section/grouping info (e.g., "project ops", "chunk ops") — you get a flat list of methods without the organizational comments that exist in the source.

---

## Comparison

| Dimension | Traditional | Arrow | Winner |
|---|---|---|---|
| Wall time | 26.4s | 8.9s | Arrow (3.0x faster) |
| Tool calls | 8 | 1 | Arrow |
| Tokens consumed | ~12,000 | ~3,550 | Arrow (3.4x less) |
| Completeness | Full source code read | Structured summary | Traditional (full context) |
| Accuracy | 100% | 90% (chunking artifact on ImportRecord/Storage) | Traditional |
| Actionability | High (can see exact code) | High (navigable index) | Tie |

**Verdict:** Arrow wins on efficiency — 3x faster, 3.4x fewer tokens, single tool call. The structured output with line ranges and token counts per method is immediately useful for navigation. The traditional approach provides perfect accuracy but at significant cost. The chunking artifact on `ImportRecord` (absorbing the schema SQL) and the `Storage` class showing as 21 tokens are minor issues that don't materially impact usefulness. For a "what's in this file" question, Arrow's file_summary is the right tool.

**Arrow advantage:** 3.0x speed, 3.4x token savings
