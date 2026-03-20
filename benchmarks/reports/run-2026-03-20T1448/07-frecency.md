# Benchmark 07 — frecency

**Query:** "How is frecency calculated and where is it applied in search ranking?"
**Category:** search_code — Hybrid search
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774010948481
**End:** 1774010964768
**Duration:** 16,287 ms

### Tool Calls
| # | Tool | Target |
|---|------|--------|
| 1 | Grep (files) | `frecency` across `/Users/andreas/arrow` |
| 2 | Grep (content) | `frecency` in `search.py` (with context) |
| 3 | Grep (content) | `frecency` in `storage.py` (with context) |
| 4 | Grep (content) | `frecency` in `server.py` (with context) |
| 5 | Grep (content) | `frecency` in `config.py` (with context) |
| 6 | Grep (content) | `frecency` in `test_frecency.py` (with context) |
| 7 | Read | `storage.py:1087-1116` (get_frecency_scores full function) |

**Total tool calls:** 7

### Answer
Frecency is calculated in `storage.py:get_frecency_scores()` using the formula:

```
score = access_count * decay
decay = 0.5 ^ (age_hours / 24)
```

Where `age_hours = (now - last_accessed) / 3600`. The decay halves every 24 hours, so recent accesses weigh more. File accesses are recorded in `storage.py:record_file_access()` which upserts into the `file_access` table (file_id, project_id, access_count, last_accessed).

Frecency is applied in `search.py:search()` after RRF fusion and dedup penalties. When `frecency_boost=True`, each chunk's score is multiplied by `(1.0 + boost)` where `boost = min(frecency_score * 0.05, 0.3)` -- capped at 30% increase. The boost is enabled via `config.py` (`frecency_boost: bool = True` in SearchConfig) and passed through `server.py:get_context()`. File accesses are recorded after each `get_context` call, creating a feedback loop where returned files rank higher in subsequent searches.

### Tokens
- Lines read: ~180 (Grep context lines) + ~30 (Read) = ~210
- Estimated tokens: ~840

### Quality
- **Quality:** 5/5 — Complete picture: exact formula with decay math, storage mechanism, application point in search pipeline, config toggle, server integration, feedback loop
- **Precision:** 95% — All tool calls were directly relevant; the test_frecency grep was supplementary but confirmed behavior

---

## Round 2 — Arrow (search_code)

**Start:** 1774010968684
**End:** 1774010979527
**Duration:** 10,843 ms

### Tool Calls
| # | Tool | Query |
|---|------|-------|
| 1 | search_code | "frecency calculation and search ranking" (limit=10, project="andreasmyleus/arrow") |

**Total tool calls:** 1

### Chunks Returned
| # | File | Symbol | Score |
|---|------|--------|-------|
| 1 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:55-61 | doc Tool Calls | 0.0857 |
| 2 | benchmarks/reports/run-2026-03-20T1815/07-frecency.md:59-65 | doc Tool Calls | 0.0818 |
| 3 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:49-93 | doc Round 2 | 0.0783 |
| 4 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:1-112 | doc full report | 0.072 |
| 5 | benchmarks/reports/run-2026-03-20T1530/07-frecency.md:76-83 | doc Answer | 0.0643 |
| 6 | benchmarks/reports/run-2026-03-20T1815/07-frecency.md:95-122 | doc Comparison | 0.0621 |
| 7 | benchmarks/reports/run-2026-03-20T1815/07-frecency.md:53-94 | doc Round 2 | 0.06 |
| 8 | benchmarks/reports/run-2026-03-20T1815/07-frecency.md:1-122 | doc full report | 0.0667 |
| 9 | benchmarks/reports/run-2026-03-20T1815/07-frecency.md:106-122 | doc Observations | 0.0692 |
| 10 | benchmarks/reports/run-2026-03-20T1815/07-frecency.md:80-84 | doc Answer | 0.0514 |

### Answer
Arrow returned **zero source code chunks**. All 10 results were from previous benchmark reports (`benchmarks/reports/run-2026-03-20T1530/07-frecency.md` and `benchmarks/reports/run-2026-03-20T1815/07-frecency.md`) -- markdown documents that *describe* the frecency implementation but are not the implementation itself. The previous reports' prose about frecency scored higher than the actual source code because they contain dense keyword co-occurrences of "frecency", "calculation", "search", and "ranking" in natural language.

While the returned text does contain the correct answer (quoted from previous benchmark analyses), no actual source code was returned. A developer would get a second-hand description, not the code.

### Tokens
- Chunks: 10
- Estimated tokens: ~5,000 (heavily overlapping chunks from two markdown files)

### Quality
- **Quality:** 1/5 — No source code returned at all. The answer is only technically recoverable by reading previous benchmark prose, which is a meta-analysis artifact, not a code search result.
- **Precision:** 0% — 0/10 chunks are source code; all are benchmark report prose from two previous runs

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 16,287 ms | 10,843 ms |
| Tool calls | 7 | 1 |
| Tokens consumed | ~840 | ~5,000 |
| Quality | 5/5 | 1/5 |
| Precision | 95% | 0% |
| Key function found | Yes (get_frecency_scores) | No (only benchmark report prose) |

### Observations

1. **Index pollution is now a compounding problem.** This is the third run of this benchmark. Two previous reports (`run-2026-03-20T1530` and `run-2026-03-20T1815`) now exist in the index, and both contain dense natural-language descriptions of frecency with the exact query terms. They completely crowd out the actual source code, which appeared in run 1 but has been absent since run 2.

2. **Self-referential feedback loop.** Each benchmark report that documents the index pollution problem becomes itself another source of pollution. The previous run's observation about index pollution (section 6: "this round demonstrates a regression") is now part of the corpus contributing to that same regression.

3. **Traditional tools are immune.** Grep + Read are unaffected by index pollution because they search raw file content and the developer chooses which files to read. The Grep results did include the benchmark report files, but it was trivial to focus on `.py` source files.

4. **Token waste is severe and worsening.** Arrow consumed ~6x more tokens than traditional, returning overlapping chunks from two markdown files that say the same thing. The ratio has worsened from run 1 (5x) to run 2 (4x token waste but 0% precision) to now.

5. **Arrow scored 4/5 in run 1, 2/5 in run 2, 1/5 in run 3.** The degradation is monotonic and directly caused by accumulating benchmark reports in the index. This confirms that `benchmarks/reports/` must be excluded from indexing.

6. **Mitigation is straightforward but unimplemented:**
   - Add `benchmarks/reports/` to `.arrowignore`
   - Or apply file-type weighting (`.py` > `.md` for code queries)
   - Or detect when all top-N results come from the same directory and diversify
