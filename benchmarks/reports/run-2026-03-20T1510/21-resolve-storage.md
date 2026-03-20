# Query 21: "Where is Storage defined and which repos have it?"

**Category:** resolve_symbol — Cross-repo
**Arrow tool under test:** `resolve_symbol`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Tool calls | 4 (Grep, Glob, Grep on clones, Read) |
| Wall time | 9,776 ms |
| Est. tokens | ~4,500 |
| Quality | 5/5 |
| Precision | 100% |

`class Storage` is defined at `src/arrow/storage.py:240` — "SQLite-backed storage with WAL mode, FTS5, and multi-project support." A separate Grep across `~/.arrow/clones/` returned no matches, confirming the symbol exists only in the `arrow` project.

---

## Round 2 — Arrow (`resolve_symbol`)

| Metric | Value |
|---|---|
| Tool calls | 1 |
| Wall time | 9,410 ms (includes tool schema fetch) |
| Est. tokens | ~800 |
| Quality | 5/5 |
| Precision | 100% |

`resolve_symbol(symbol="Storage", project="andreasmyleus/arrow")` returned 1 result: `class Storage` at `src/arrow/storage.py:240-241` in project `andreasmyleus/arrow`. No other indexed projects define this symbol.

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|---|---|---|---|
| Tool calls | 4 | 1 | Arrow |
| Wall time (ms) | 9,776 | 9,410 | Tie |
| Est. tokens | ~4,500 | ~800 | Arrow |
| Quality | 5/5 | 5/5 | Tie |
| Precision | 100% | 100% | Tie |

**Summary:** Both approaches found the same result with identical quality. Arrow's advantage is in simplicity (1 call vs 4) and token efficiency (~82% reduction). Wall time was comparable because the traditional approach used parallel tool calls effectively. The cross-repo aspect is where `resolve_symbol` truly shines — it automatically searched all indexed projects in a single call, whereas the traditional approach required a separate Grep against `~/.arrow/clones/` and would miss repos not cloned locally.
