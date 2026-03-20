# Benchmark 07 — frecency

**Query:** "How is frecency calculated and where is it applied in search ranking?"
**Category:** search_code — Hybrid search
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774007818076
**End:** 1774007828184
**Duration:** 10,108 ms

### Tool Calls
| # | Tool | Target |
|---|------|--------|
| 1 | Grep | `frecency` across `/Users/andreas/arrow` |
| 2 | Read | `storage.py:1045-1104` (record_file_access + get_frecency_scores) |
| 3 | Read | `search.py:475-509` (frecency boost application) |
| 4 | Read | `search.py:385-404` (search method signature) |
| 5 | Read | `storage.py:385-414` (migration schema for file_access table) |
| 6 | Read | `server.py:823-842` (get_context calling frecency) |

**Total tool calls:** 6

### Answer
Frecency is calculated in `storage.py:get_frecency_scores()` using the formula:

```
score = access_count * decay
decay = 0.5 ^ (age_hours / 24)
```

Where `age_hours = (now - last_accessed) / 3600`. The decay halves every 24 hours, so recent accesses weigh more. File accesses are recorded in `storage.py:record_file_access()` which upserts into the `file_access` table (file_id, access_count, last_accessed).

Frecency is applied in `search.py:search()` after RRF fusion and dedup penalties. When `frecency_boost=True`, each chunk's score is multiplied by `(1.0 + boost)` where `boost = min(frecency_score * 0.05, 0.3)` — capped at 30% increase. The boost is enabled via `config.py` (`frecency_boost = true` in arrow.toml) and passed through `server.py:get_context()`. File accesses are recorded after each `get_context` call, creating a feedback loop where returned files rank higher in subsequent searches.

### Tokens
- Lines read: ~155
- Estimated tokens: ~620

### Quality
- **Quality:** 5/5 — Complete picture: formula, storage, application point, config, feedback loop
- **Precision:** 95% — All reads were directly relevant; one read (migration schema) was supplementary

---

## Round 2 — Arrow (search_code)

**Start:** 1774007831157
**End:** 1774007838248
**Duration:** 7,091 ms

### Tool Calls
| # | Tool | Query |
|---|------|-------|
| 1 | search_code | "frecency calculation and search ranking" (limit=10) |

**Total tool calls:** 1

### Chunks Returned
| # | File | Symbol | Score |
|---|------|--------|-------|
| 1 | tests/test_frecency.py:19-44 | test_frecency_boost_in_search | 0.0525 |
| 2 | src/arrow/storage.py:1048-1062 | record_file_access | 0.0462 |
| 3 | src/arrow/search.py:668-784 | get_context | 0.0400 |
| 4 | src/arrow/config.py:36-88 | load | 0.0387 |
| 5 | tests/test_core.py:581-607 | test_filename_boost_in_ranking | 0.0382 |
| 6 | src/arrow/server.py:767-877 | get_context (server) | 0.0375 |
| 7 | src/arrow/search.py:112-134 | _filename_match_boost | 0.0364 |
| 8 | src/arrow/search.py:385-629 | search | 0.0353 |
| 9 | tests/test_frecency.py:46-57 | test_frecency_decay | 0.0332 |
| 10 | demo_comparison.py:33-89 | header + SCENARIOS | 0.0300 |

### Answer
Arrow returned the complete picture across 10 chunks:
- **Calculation:** `storage.py:record_file_access` shows the upsert logic (access_count + last_accessed). The `get_frecency_scores` function was NOT directly returned as a chunk, though it appears inline within the `search()` method chunk.
- **Application:** `search.py:search()` (chunk 8) contains the full frecency boost logic: `boost = min(frecency[fid] * 0.05, 0.3)`, applied as `score * (1.0 + boost)` after RRF fusion.
- **Config:** `config.py:load()` shows `frecency_boost` being read from TOML.
- **Server integration:** `server.py:get_context` shows the call chain and file access recording.
- **Decay formula:** Visible within the `search()` chunk calling `get_frecency_scores`, and the test `test_frecency_decay` confirms decay behavior.

### Tokens
- Chunks: 10
- Estimated tokens: ~3,200 (large due to full `search()` function at 244 lines)

### Quality
- **Quality:** 4/5 — All key pieces present but `get_frecency_scores()` (the actual formula) was not returned as its own chunk; it's only referenced indirectly. Two chunks were noise (demo_comparison.py, _filename_match_boost).
- **Precision:** 70% — 7/10 chunks directly relevant; config.load is partially relevant, _filename_match_boost and demo_comparison.py are tangential

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 10,108 ms | 7,091 ms |
| Tool calls | 6 | 1 |
| Tokens consumed | ~620 | ~3,200 |
| Quality | 5/5 | 4/5 |
| Precision | 95% | 70% |
| Key function found | Yes (get_frecency_scores) | Indirectly (within search() chunk) |

### Observations

1. **Arrow was faster** (7.1s vs 10.1s) and required only 1 tool call vs 6, reducing agent round-trips.
2. **Traditional was more precise** — targeted reads yielded exactly the relevant code with minimal noise. The Grep scan identified all 50+ mentions, allowing surgical reads of only the core functions.
3. **Arrow missed the core formula** — `get_frecency_scores()` (the 27-line function with the actual `score = access_count * decay` formula) was not returned as its own chunk. Instead, the `record_file_access` function was returned (records access but not the calculation). The formula was only visible because the massive `search()` function chunk happened to call it.
4. **Token cost tradeoff** — Arrow consumed ~5x more tokens due to returning full function bodies (especially the 244-line `search()` method). Traditional approach was far more token-efficient.
5. **Noise in Arrow results** — `demo_comparison.py` and `_filename_match_boost` were not relevant to the frecency question, lowering precision. The test chunks, while confirming behavior, added bulk.
6. **This query type favors traditional tools** — "How is X calculated" queries benefit from Grep's ability to pinpoint the exact definition, then surgical Read of just that function. Arrow's chunk-level granularity sometimes misses small but critical functions when they're overshadowed by larger neighbors.
