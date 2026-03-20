# Query 21: "Where is `Storage` defined and which repos have it?"

Category: Cross-repo symbol resolution
Arrow tool(s) under test: resolve_symbol

## Round 1 — Traditional

**Timestamps:** start=1774009945795 end=1774009956898
**Wall time:** 11103ms
**Tool calls:** 4 (Grep x2, Glob x1, Read x1)
**Tokens from content:** ~100 (15 lines read from storage.py x ~4 tokens + grep output lines)
**Answer quality:** 5
**Precision:** 100%

### Answer

`class Storage` is defined at `src/arrow/storage.py:240`. It is described as "SQLite-backed storage with WAL mode, FTS5, and multi-project support." No other indexed repos (checked `~/.arrow/clones/`) contain a `class Storage` definition — it exists only in the `arrow` project.

### Files read
- /Users/andreas/arrow/src/arrow/storage.py (lines 238-252)

## Round 2 — Arrow

**Timestamps:** start=1774009960165 end=1774009970040
**Wall time:** 9875ms
**Tool calls:** 1 (resolve_symbol x1)
**Tokens from content:** ~30 (Arrow-reported: 2-line definition + metadata)
**Chunks returned:** 1
**Answer quality:** 5
**Precision:** 100%

### Answer

`class Storage` is defined at `src/arrow/storage.py:240-241` in project `andreasmyleus/arrow`. 1 result across all indexed projects — no other repos contain this symbol.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 11103ms | 9875ms |
| Tool calls | 4 | 1 |
| Tokens consumed | ~100 | ~30 |
| Quality | 5/5 | 5/5 |
| Precision | 100% | 100% |

### Notes

Both approaches found the same result: `class Storage` defined at `src/arrow/storage.py:240` with no matches in other repos. The Arrow `resolve_symbol` tool provided the answer in a single call, automatically searching across all indexed projects. The traditional approach required two separate Grep calls (one for the local repo, one for `~/.arrow/clones/`), a Glob to find storage files, and a Read to confirm the definition. Arrow was slightly faster (1.2s) and used 75% fewer tool calls. The key advantage of `resolve_symbol` is that cross-repo resolution is built in — no need to manually enumerate and search other repos.
