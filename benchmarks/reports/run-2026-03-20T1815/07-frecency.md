# Benchmark 07 — frecency

**Query:** "How is frecency calculated and where is it applied in search ranking?"
**Category:** search_code — Hybrid search
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774009867972
**End:** 1774009884258
**Duration:** 16,286 ms

### Tool Calls
| # | Tool | Target |
|---|------|--------|
| 1 | Grep (files) | `frecency` across `/Users/andreas/arrow` |
| 2 | Grep (content) | `frecency` in `search.py` |
| 3 | Grep (content) | `frecency` in `storage.py` |
| 4 | Grep (content) | `frecency` in `server.py` |
| 5 | Grep (content) | `frecency` in `config.py` |
| 6 | Grep (content) | `frecency` in `test_frecency.py` |
| 7 | Read | `storage.py:1074-1123` (record_file_access + get_frecency_scores) |
| 8 | Read | `search.py:495-529` (frecency boost application in search()) |
| 9 | Read | `search.py:690-749` (get_context method with frecency param) |
| 10 | Read | `server.py:850-869` (get_context call + file access recording) |

**Total tool calls:** 10

### Answer
Frecency is calculated in `storage.py:get_frecency_scores()` using the formula:

```
score = access_count * decay
decay = 0.5 ^ (age_hours / 24)
```

Where `age_hours = (now - last_accessed) / 3600`. The decay halves every 24 hours, so recent accesses weigh more. File accesses are recorded in `storage.py:record_file_access()` which upserts into the `file_access` table (file_id, access_count, last_accessed).

Frecency is applied in `search.py:search()` after RRF fusion and dedup penalties. When `frecency_boost=True`, each chunk's score is multiplied by `(1.0 + boost)` where `boost = min(frecency_score * 0.05, 0.3)` -- capped at 30% increase. The boost is enabled via `config.py` (`frecency_boost = true` in arrow.toml) and passed through `server.py:get_context()`. File accesses are recorded after each `get_context` call, creating a feedback loop where returned files rank higher in subsequent searches.

### Tokens
- Lines read: ~155 (Grep content lines) + ~125 (Read lines) = ~280
- Estimated tokens: ~1,120

### Quality
- **Quality:** 5/5 — Complete picture: exact formula, storage mechanism, application point, config toggle, server integration, feedback loop
- **Precision:** 95% — All reads directly relevant; test file grep was supplementary but confirmed behavior

---

## Round 2 — Arrow (search_code)

**Start:** 1774009887912
**End:** 1774009895195
**Duration:** 7,283 ms

### Tool Calls
| # | Tool | Query |
|---|------|-------|
| 1 | search_code | "frecency calculation and search ranking" (limit=10, project="andreasmyleus/arrow") |

**Total tool calls:** 1

### Chunks Returned
| # | File | Symbol | Score |
|---|------|--------|-------|
| 1 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:55-61 | doc Tool Calls | 0.0857 |
| 2 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:49-93 | doc Round 2 | 0.0818 |
| 3 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:1-112 | doc full report | 0.075 |
| 4 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:76-83 | doc Answer | 0.072 |
| 5 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:62-75 | doc Chunks Returned | 0.06 |
| 6 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:94-112 | doc Comparison | 0.0545 |
| 7 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:105-112 | doc Observations | 0.0529 |
| 8 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:9-48 | doc Round 1 | 0.05 |
| 9 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:27-38 | doc Answer | 0.0474 |
| 10 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:15-26 | doc Tool Calls | 0.0462 |

### Answer
Arrow returned **zero source code chunks**. All 10 results were from the previous benchmark report (`benchmarks/reports/run-2026-03-20T1530/07-frecency.md`), which is a markdown document that *describes* the frecency implementation but is not the implementation itself. The previous report's text about frecency scored higher than the actual source code because it contains dense keyword matches for both "frecency" and "search ranking" in natural language prose.

While the returned report text does contain the correct answer (quoted from the previous round's analysis), this is an index pollution problem -- benchmark reports that discuss source code outrank the actual source code.

### Tokens
- Chunks: 10
- Estimated tokens: ~4,500 (heavily overlapping chunks from same markdown file)

### Quality
- **Quality:** 2/5 — The answer to the question is technically present in the returned text (because it quotes the previous benchmark), but no actual source code was returned. A developer wanting to understand the implementation would get a second-hand description, not the code.
- **Precision:** 0% — 0/10 chunks are source code; all are benchmark report prose

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 16,286 ms | 7,283 ms |
| Tool calls | 10 | 1 |
| Tokens consumed | ~1,120 | ~4,500 |
| Quality | 5/5 | 2/5 |
| Precision | 95% | 0% |
| Key function found | Yes (get_frecency_scores) | No (only benchmark report prose) |

### Observations

1. **Index pollution is a critical issue.** The previous benchmark report (`07-frecency.md`) discussing frecency ranked higher than the actual source code because it contains dense, natural-language descriptions with the exact query terms "frecency", "calculation", "search", and "ranking" co-occurring frequently. This is a known failure mode of BM25 + semantic search when documentation/reports about code are indexed alongside the code itself.

2. **Arrow was faster** (7.3s vs 16.3s) and required only 1 tool call vs 10, but the speed advantage is meaningless when the results contain no source code.

3. **Traditional tools were surgical and accurate.** Grep identified all files mentioning "frecency", then targeted Read calls extracted the exact functions: the formula in `get_frecency_scores()`, the boost application in `search()`, the config toggle, and the server integration. Every read was productive.

4. **Token waste was severe in Arrow.** The 10 returned chunks were heavily overlapping sections of the same 112-line markdown file, consuming ~4,500 tokens to deliver essentially the same content repeated multiple times.

5. **Mitigation strategies for index pollution:**
   - Exclude `benchmarks/reports/` from indexing (via `.arrowignore` or config)
   - Apply file-type weighting that prioritizes `.py` files over `.md` for code queries
   - Detect and penalize when all top results come from the same file
   - Use query classification to route "how is X implemented" queries to source code files

6. **This round demonstrates a regression** compared to the previous run (run-2026-03-20T1530) where Arrow scored 4/5 on this same query. The difference is that the previous run's report is now indexed, creating a self-referential ranking problem.
