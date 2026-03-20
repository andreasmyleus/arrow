# Query 24: Storage.py — Structure, Classes, Methods

**Category:** File overview
**Query:** "What's in storage.py — structure, classes, methods?"
**Arrow tool tested:** `file_summary`

## Round 1 — Traditional Tools

| Metric | Value |
|---|---|
| Wall time | 28,256 ms |
| Tool calls | 8 (7 Read + 1 Glob/Bash) |
| Tokens consumed | ~5,660 (1,415 lines x ~4 tokens) |
| Quality | 5/5 |
| Precision | 100% |

**Method:** Read the entire file in 7 sequential chunks (200 lines each) due to the 10k token limit per read. Had to page through all 1,454 lines to get a complete picture.

**Findings:**
- 5 dataclasses: `ProjectRecord`, `FileRecord`, `ChunkRecord`, `SymbolRecord`, `ImportRecord`
- 1 main class: `Storage` with 57 methods across ~1,200 lines
- Schema SQL constant `SCHEMA_V2_SQL` (~165 lines) defining 9 tables, 3 FTS triggers, 7 indexes
- Methods organized in sections: project ops, file ops, chunk ops, symbol ops, stats, frecency, tool analytics, session/context, long-term memory, stale detection, dead code detection
- Schema versioning with 3 migration methods (v1->v2, v2->v3, v3->v4)

## Round 2 — Arrow `file_summary`

| Metric | Value |
|---|---|
| Wall time | 7,714 ms |
| Tool calls | 1 |
| Tokens returned | ~2,800 (structured JSON) |
| Quality | 4/5 |
| Precision | 90% |

**Findings:** Returned structured JSON with:
- 6 classes listed (including dataclasses and Storage)
- 57 functions with line ranges and token counts
- 11 imports listed
- Total tokens: 10,923 across 63 chunks

**Minor issues:**
- `ImportRecord` class shows incorrect line range (68-237) — it bleeds into the `SCHEMA_V2_SQL` constant, suggesting the chunker grouped the dataclass with the following module-level SQL string
- `Storage` class only shows lines 240-241 (class signature) rather than 240-1454 (full body) — the methods are listed separately under "functions" rather than nested under the class
- No explicit mention of the `SCHEMA_V2_SQL` constant or the schema structure (tables, triggers, indexes)
- Does not show method groupings/sections or the conceptual organization

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Wall time | 28,256 ms | 7,714 ms |
| Tool calls | 8 | 1 |
| Tokens consumed | ~5,660 | ~2,800 |
| Quality | 5/5 | 4/5 |
| Precision | 100% | 90% |

**Speedup:** 3.7x faster
**Token savings:** 51% fewer tokens

## Verdict

Arrow's `file_summary` is significantly faster and more efficient for getting a structural overview of a file. The structured JSON output with line ranges and token counts per function is immediately useful. However, the traditional approach gave a fuller picture: it revealed the schema SQL constant, the table definitions, the migration logic details, and the conceptual grouping of methods into sections. The chunker artifact where `ImportRecord` bleeds into `SCHEMA_V2_SQL` is a minor accuracy issue. For a quick "what's in this file" question, Arrow is the clear winner; for deep understanding of the file's internals, the traditional read-through remains more thorough.
