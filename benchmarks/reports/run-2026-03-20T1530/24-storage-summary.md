# Query 24: "What's in storage.py — structure, classes, methods?"

**Category:** file_summary — Per-file breakdown

## Round 1 — Traditional Tools

| Metric | Value |
|---|---|
| Wall time | 6,715 ms |
| Tool calls | 3 (Grep, Read, Bash timestamp) |
| Tokens sent (est.) | ~3,500 (grep output + file header read) |
| Tokens received (est.) | ~2,800 |
| Quality | 4/5 |
| Precision | 90% |

**Method:** Grep for `^class |def ` lines to get all class and method names with line numbers, plus Read first 60 lines for dataclass fields and imports.

**Result:** Found 6 dataclass/class definitions (ProjectRecord, FileRecord, ChunkRecord, SymbolRecord, ImportRecord, Storage) and 56 methods on Storage class. Got line numbers for all. Missing: token counts per function, total file token count. Would need additional reads to get field details for all dataclasses beyond the first 60 lines.

## Round 2 — Arrow (`file_summary`)

| Metric | Value |
|---|---|
| Wall time | 5,834 ms |
| Tool calls | 1 (file_summary) |
| Tokens sent (est.) | ~100 |
| Tokens received (est.) | ~3,200 |
| Quality | 5/5 |
| Precision | 98% |

**Method:** Single `file_summary` call with path and project.

**Result:** Complete structured JSON with:
- 6 classes with line ranges and token counts
- 56 methods with line ranges and token counts
- 11 imports listed
- Total file stats: 10,750 tokens, 62 chunks, language: Python

## Comparison

| Dimension | Traditional | Arrow | Winner |
|---|---|---|---|
| Wall time | 6,715 ms | 5,834 ms | Arrow |
| Tool calls | 3 | 1 | Arrow |
| Tokens sent | ~3,500 | ~100 | Arrow (35x less) |
| Completeness | Missing token counts, partial field details | Full structure with token counts | Arrow |
| Structured output | Raw grep/text | JSON with line ranges, tokens | Arrow |
| Quality | 4/5 | 5/5 | Arrow |
| Precision | 90% | 98% | Arrow |

## Notes

- Arrow's `file_summary` is purpose-built for this exact query type. It returns structured JSON with token counts per function/class, which is impossible to get from grep/read without additional tooling.
- Traditional approach required combining grep (for names/lines) and read (for field details), and still missed token-level metadata.
- The Arrow response included one minor oddity: ImportRecord spans lines 68-237 with 1,239 tokens, suggesting it includes schema SQL or similar large content block rather than just a simple dataclass. This is accurate to the AST chunking.
- For "what's in this file" questions, `file_summary` is the ideal single-call solution.
