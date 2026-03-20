# Query 28: Binary File Detection

**Query:** "How does Arrow detect and skip binary files during indexing?"
**Category:** get_context — Needle
**Arrow tool under test:** get_context

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 41,586 ms |
| Tool calls | 7 |
| Tokens (est.) | ~4,500 |
| Quality | 5/5 |
| Precision | 100% |

### Findings

Arrow uses a **three-layer** approach to detect and skip binary files during indexing:

1. **Extension-based filtering** (`discovery.py` lines 11-78): The `DEFAULT_IGNORE` set contains ~50 patterns including binary extensions like `*.so`, `*.dylib`, `*.dll`, `*.exe`, `*.o`, `*.a`, `*.class`, `*.jar`, `*.wasm`, `*.png`, `*.jpg`, `*.mp4`, `*.pdf`, `*.zip`, `*.db`, `*.sqlite`, etc. Matched via `fnmatch` in `_should_ignore()`.

2. **Null-byte content sniffing** (`discovery.py` lines 182-189): After extension filtering, `discover_files()` reads the first 512 bytes of each file in binary mode and checks for `b"\x00"`. If a null byte is found, the file is skipped. This catches binary files with non-standard extensions.

3. **Size guard** (`discovery.py` lines 173-180): Files larger than `MAX_FILE_SIZE` (1 MB) or empty files (0 bytes) are skipped before the binary check.

Additionally, in `git_utils.py` (line 136-138), when reading file content from git commits, binary files are skipped via `UnicodeDecodeError` — if `result.stdout.decode("utf-8")` fails, the exception is caught and `None` is returned.

In the indexer itself (`indexer.py` line 156), files are read with `encoding="utf-8", errors="replace"`, which means any binary content that slips through would have replacement characters but wouldn't crash.

### Files examined
- `/Users/andreas/arrow/src/arrow/discovery.py` (primary — all three layers)
- `/Users/andreas/arrow/src/arrow/git_utils.py` (git commit binary skip)
- `/Users/andreas/arrow/src/arrow/indexer.py` (utf-8 fallback)

---

## Round 2 — Arrow (get_context)

| Metric | Value |
|---|---|
| Wall time | 8,440 ms |
| Tool calls | 1 |
| Tokens (est.) | 0 (no results returned) |
| Chunks returned | 0 |
| Quality | 1/5 |
| Precision | 0% |

### Findings

`get_context` returned **no results** for this query. The response was:

> No results for: How does Arrow detect and skip binary files during indexing?

The binary detection logic lives in `discovery.py` within the `discover_files()` function. The null-byte check is a small section (lines 182-189) embedded within a larger function, which may not have been chunked as a standalone semantic unit. The `DEFAULT_IGNORE` set is a module-level constant, not a function or class, which may also be difficult for the search to associate with a "binary detection" query.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 41,586 ms | 8,440 ms |
| Tool calls | 7 | 1 |
| Tokens (est.) | ~4,500 | ~50 |
| Quality | 5/5 | 1/5 |
| Precision | 100% | 0% |
| Complete answer | Yes | No |

### Verdict

**Traditional wins.** Arrow returned zero results for this query, completely failing to surface the binary detection logic. The traditional approach found all three layers of binary file handling across three files.

This is a case where the needle (binary detection) is a small piece of logic embedded within larger functions (`discover_files`) and module-level constants (`DEFAULT_IGNORE`). The query concept "binary files" may not appear prominently enough in the chunk text or embeddings to rank above the relevance threshold. The actual code uses terms like `b"\x00"`, `"rb"`, and extension patterns rather than the word "binary" — only a single comment on line 182 says "Skip binary files (quick check)".

**Failure mode:** Relevance threshold too aggressive for a cross-cutting concept that is implemented implicitly (null-byte checks, extension lists) rather than explicitly (no `is_binary()` function or `BinaryDetector` class).
