# Query 21: Where is `Storage` defined and which repos have it?

**Category:** Cross-repo
**Arrow tool(s):** `resolve_symbol`
**Date:** 2026-03-20

## Round 1 — Traditional (Glob / Grep / Read)

| Metric       | Value |
|-------------|-------|
| Wall time    | 20,012 ms |
| Tool calls   | 4 (Grep x2, Read, Bash ls) |
| Tokens (est.)| ~100 |
| Quality      | 5/5 |
| Precision    | 100% |

**Steps:**
1. Grep for `class Storage` across the entire working directory — found `src/arrow/storage.py:240`.
2. Read the file at that line to confirm the definition and docstring.
3. Listed repos in `~/.arrow/clones/` (encode, fastapi, pydantic).
4. Grep for `class Storage` across all cloned repos — no matches.

**Result:** `class Storage` is defined at `src/arrow/storage.py:240`. Docstring: "SQLite-backed storage with WAL mode, FTS5, and multi-project support." No other indexed repos contain a `class Storage` definition.

## Round 2 — Arrow (`resolve_symbol`)

| Metric       | Value |
|-------------|-------|
| Wall time    | 10,664 ms |
| Tool calls   | 1 |
| Tokens (est.)| ~16 |
| Chunks       | 1 |
| Quality      | 5/5 |
| Precision    | 100% |

**Steps:**
1. Called `resolve_symbol(symbol="Storage", project="andreasmyleus/arrow")`.

**Result:** `class Storage` at `src/arrow/storage.py:240-241` in project `andreasmyleus/arrow`. 1 result across all indexed projects — no other repos define this symbol.

## Comparison

| Metric        | Traditional | Arrow   | Delta  |
|--------------|------------|---------|--------|
| Wall time     | 20,012 ms  | 10,664 ms | -47%  |
| Tool calls    | 4          | 1        | -75%   |
| Tokens (est.) | ~100       | ~16      | -84%   |
| Quality       | 5/5        | 5/5      | Tie    |
| Precision     | 100%       | 100%     | Tie    |

## Notes

- The traditional approach required manually discovering cloned repos and searching each location separately. Arrow's `resolve_symbol` handles cross-repo resolution in a single call, searching all indexed projects automatically.
- Both approaches produced identical answers. The cross-repo question is where Arrow shines most — it knows about all indexed projects and can scan them without the user needing to know where clones live.
- Token savings are significant (84%) because the traditional Grep returned noisy matches from prior benchmark report files, while Arrow returned only the definition.
