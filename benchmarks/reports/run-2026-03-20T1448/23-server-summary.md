# Query 23: Server.py File Overview

**Category:** File overview
**Query:** "Give me an overview of server.py — what functions does it have, how big is it?"
**Arrow tool(s) under test:** `file_summary`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 15,495 ms |
| Tool calls | 6 (wc -l, grep functions, grep classes, grep imports, read top, timestamp) |
| Tokens in | ~196 (~49 lines) |
| Quality | 4/5 |
| Precision | 85% |

**Approach:** Used `wc -l` for line count (1,169 lines), `grep` with `^(async )?def` pattern for function definitions (27 hits), `grep` for class definitions (0 hits), `grep` for import lines (18 hits), and `Read` to get the module docstring.

**What it found:**
- 1,169 lines total
- 27 top-level/nested function definitions
- 0 classes
- 18 import statements
- Module-level docstring

**Gaps:** No token counts per function. No line ranges per function (only starting line numbers). Missed the nested `on_change` and `_warm` functions that are defined inside other functions. Would need additional Read calls to get function sizes or understand grouping.

---

## Round 2 — Arrow (`file_summary`)

| Metric | Value |
|--------|-------|
| Wall time | 10,491 ms |
| Tool calls | 1 |
| Tokens in | ~600 (structured JSON) |
| Chunks | 30 |
| Quality | 5/5 |
| Precision | 95% |

**What it found:**
- 8,201 total tokens across 30 chunks
- 30 functions with exact line ranges and per-function token counts
- 0 classes
- Full import list (stdlib, third-party, internal)
- Nested functions (`on_change` lines 128-157, `_warm` lines 1077-1114) correctly identified
- Largest functions: `get_context` (1,001 tokens, lines 792-902), `search_structure` (962 tokens, lines 906-1043), `search_regex` (652 tokens, lines 514-589)

**Minor issue:** Import parsing includes some noqa comment artifacts (e.g., `"( # noqa: F401"`) — cosmetic, not functional.

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Wall time | 15,495 ms | 10,491 ms | Arrow (1.5x faster) |
| Tool calls | 6 | 1 | Arrow (6x fewer) |
| Tokens in | ~196 | ~600 | Traditional (3x less) |
| Completeness | Partial | Full | Arrow |
| Per-function sizing | No | Yes (token counts + line ranges) | Arrow |
| Nested function detection | Missed 2 | Found all 30 | Arrow |

## Verdict

**Arrow wins on completeness and convenience.** A single `file_summary` call returned structured data with per-function token counts and line ranges — information that would require many additional Read calls to reconstruct traditionally. The Traditional approach was cheaper in raw tokens returned but missed nested functions and provided no sizing information beyond line numbers. Arrow returned more tokens but the data was structured JSON, making it immediately actionable. The 1.5x speed advantage is modest but consistent with Arrow pre-computing AST-level metadata at index time. For a "give me an overview" use case, `file_summary` is purpose-built and clearly superior.
