# Query 22: Find all definitions of search across indexed repos

**Category:** resolve_symbol — Cross-repo
**Arrow tool under test:** `resolve_symbol`
**Query:** "Find all definitions of search across indexed repos"

---

## Round 1 — Traditional (Glob + Grep + Read)

**Time:** 9,906 ms (1774012364735 to 1774012374641)
**Tool calls:** 3 (Grep x3)
**Estimated tokens:** ~4,500 (grep output was noisy with benchmark report matches)

**Method:** Grep for `def search` across `/Users/andreas/arrow/src` and `~/.arrow/clones/` (pydantic). Required separate grep calls and manual filtering of results.

**Results found (exact `search` definitions):**
1. `src/arrow/search.py:404` — `def search(...)` HybridSearcher method
2. `src/arrow/vector_store.py:61` — `def search(...)` VectorStore method

**Prefix matches also returned (not exact "search"):**
- `storage.py:720` — `def search_fts(...)`
- `storage.py:755` — `def search_regex(...)`
- `storage.py:810` — `def search_symbols(...)`
- `server.py:472` — `def search_code(...)`
- `server.py:523` — `def search_regex(...)`
- `server.py:915` — `def search_structure(...)`

**Cross-repo results:**
- `pydantic/aliases.py:39` — `def search_dict_for_path(...)` (prefix match, not exact)

**False positives in output:** Many matches from benchmark report markdown files and test fixture strings (`tests/test_core.py`, `tests/test_precision.py`), requiring manual filtering.

**Quality:** 3/5 — Found the definitions but required significant manual filtering. Grep has no concept of "exact symbol name" vs prefix match, and no AST awareness to distinguish real definitions from string literals. No source code bodies returned without additional Read calls.
**Precision:** 25% (2 exact matches out of ~8 source-code grep hits, plus noise from reports and tests)

---

## Round 2 — Arrow (`resolve_symbol`)

**Time:** 9,755 ms (1774012380118 to 1774012389873)
**Tool calls:** 1
**Estimated tokens:** ~1,800 (3 results with code bodies)

**Results (3):**
1. `arrow.toml:9-32` — config `[search]` section (config block, not a function)
2. `src/arrow/vector_store.py:61-75` — `def search(...)` VectorStore method (full code body)
3. `src/arrow/search.py:404-654` — `def search(...)` HybridSearcher method (full code body, truncated at ~250 lines)

**Cross-repo:** Only searched within `andreasmyleus/arrow`. Pydantic had no exact `search` symbol, so correctly excluded.

**Quality:** 4/5 — Correctly resolved the 2 exact `search` function definitions with full code bodies. The config section match (arrow.toml `[search]`) is a minor false positive. Did not return prefix matches (search_fts, search_code, etc.), demonstrating AST-level symbol resolution. However, only one indexed repo (arrow) was searched — pydantic was indexed but had no exact match, which is correct behavior.
**Precision:** 67% (2 correct function definitions out of 3 results)

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Time (ms) | 9,906 | 9,755 |
| Tool calls | 3 | 1 |
| Tokens (est.) | ~4,500 | ~1,800 |
| Results | 2 exact + 6 prefix + noise | 2 exact + 1 config |
| Code bodies | No (signatures only) | Yes (full source) |
| Quality | 3/5 | 4/5 |
| Precision | 25% | 67% |

**Winner:** Arrow

**Analysis:**
- **Similar speed** — both took ~10 seconds, which is unusually slow for both approaches. The Arrow tool likely spent time scanning across indexed projects.
- **Arrow was far more precise** — it correctly identified only the 2 exact `search` function definitions, while grep returned 8+ prefix matches and numerous false positives from test fixtures and benchmark reports. The only Arrow false positive was a TOML config section named `[search]`.
- **Arrow returned full code bodies** — Traditional grep only showed signatures; getting the full source would require additional Read calls (more tool calls, more tokens).
- **Token efficiency** — Arrow used ~60% fewer tokens due to no noise from report files and test fixtures.
- **Cross-repo behavior** — Arrow searched all indexed repos but only arrow had exact `search` symbols. Traditional required separate grep calls per directory and found only a prefix match in pydantic.
