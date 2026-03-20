# Query 07: Frecency Calculation and Application

**Query:** "How is frecency calculated and where is it applied in search ranking?"
**Category:** search_code — Hybrid search
**Arrow tool under test:** `search_code`

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774012294096
**End:** 1774012315233
**Duration:** 21,137 ms

### Method
1. `Grep` for "frecency" across `src/` — found all references (content mode)
2. `Grep` for "frecency" across `tests/` — found test files
3. `Read` storage.py:1070-1130 — `record_file_access` and `get_frecency_scores` functions
4. `Read` search.py:495-535 — frecency boost application in `search()`
5. `Read` search.py:405-425 — `search()` signature with `frecency_boost` parameter
6. `Read` server.py:855-879 — where frecency is triggered and file access recorded
7. `Read` search.py:690-730 — `get_context()` passing frecency_boost through
8. `Grep` for "file_access" in storage.py — found table schema reference
9. `Read` storage.py:157-168 — `file_access` table DDL

### Answer Found
Frecency is calculated in `storage.py:get_frecency_scores()` as:
- **Score = access_count * recency_decay**, where decay = 0.5^(age_hours / 24) — i.e., the score halves every 24 hours.
- File accesses are tracked in the `file_access` table (file_id, access_count, last_accessed).
- `record_file_access()` increments access_count and updates last_accessed via upsert.

Applied in search ranking (`search.py:501-525`):
- After reciprocal rank fusion and dedup, if `frecency_boost=True`, scores are boosted up to **30% max** (`boost = min(frecency[fid] * 0.05, 0.3)`).
- The boost is multiplicative: `score = score * (1.0 + boost)`.
- Results are re-sorted after boosting.

Triggered from `server.py:863` where `cfg.search.frecency_boost` (default `True` in config.py) is passed through `get_context()` -> `search()`. After results are returned, `server.py:871-876` records file access for future frecency calculations.

### Metrics
| Metric | Value |
|--------|-------|
| Tool calls | 9 |
| Estimated tokens | ~4,500 |
| Quality | 5/5 |
| Precision | 100% |
| Notes | Systematic grep-first approach found all relevant code quickly |

---

## Round 2 — Arrow (`search_code`)

**Start:** 1774012317440
**End:** 1774012331918
**Duration:** 14,478 ms

### Method
1. `search_code("How is frecency calculated and where is it applied in search ranking?")` — returned 0 results (natural language query too verbose)
2. `search_code("frecency score calculation boost search", limit=10)` — returned 10 results

### Results Returned (10 chunks)
1. `tests/test_frecency.py:19-44` — `test_frecency_boost_in_search` (score=0.0548)
2. `src/arrow/search.py:404-654` — `search()` full function (score=0.0545)
3. `src/arrow/search.py:693-785` — `get_context()` full function (score=0.05)
4. `src/arrow/search.py:124-153` — `_filename_match_boost` (score=0.048)
5. `src/arrow/config.py:36-88` — `load()` config function (score=0.0414)
6. `tests/test_core.py:581-607` — `test_filename_boost_in_ranking` (score=0.04)
7. `tests/test_frecency.py:46-57` — `test_frecency_decay` (score=0.036)
8. `src/arrow/config.py:14-18` — `SearchConfig` class (score=0.0316)
9. `src/arrow/search.py:175-183` — `SearchResult` class (score=0.0308)
10. `src/arrow/storage.py:720-753` — `search_fts()` function (score=0.03)

### Answer Quality
The Arrow results contain the key `search()` function (chunk 2) which includes the full frecency boost logic (lines 501-525). The `get_context()` function (chunk 3) shows how frecency_boost is passed through. The `SearchConfig` (chunk 8) shows the default config. Test files (chunks 1, 6, 7) confirm behavior.

**Missing:** `storage.py:get_frecency_scores()` and `record_file_access()` — the actual frecency calculation formula and the recording mechanism were not returned. The `search_fts` function (chunk 10) and `_filename_match_boost` (chunk 4) are tangential. The `SearchResult` dataclass (chunk 9) adds no value to this query.

### Metrics
| Metric | Value |
|--------|-------|
| Tool calls | 2 (1 failed, 1 successful) |
| Tokens (response) | ~5,800 |
| Chunks returned | 10 |
| Quality | 3/5 |
| Precision | 60% |
| Notes | Missing the core `get_frecency_scores()` calculation; 4 of 10 results are noise |

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 21,137 ms | 14,478 ms |
| Tool calls | 9 | 2 |
| Est. tokens | ~4,500 | ~5,800 |
| Quality | 5/5 | 3/5 |
| Precision | 100% | 60% |
| Completeness | Full picture | Missing storage layer |

### Analysis

**Speed:** Arrow was ~6.7 seconds faster (32% less wall time), though the first natural-language query returned 0 results and required a reformulated keyword query.

**Quality gap:** The traditional approach delivered a complete answer covering all three layers: (1) the frecency formula in `storage.py`, (2) the boost application in `search.py`, and (3) the integration point in `server.py`. Arrow returned the search and config layers but missed the storage layer entirely — `get_frecency_scores()` with its `access_count * 0.5^(age_hours/24)` formula was absent from results. This is the most important piece for answering "how is frecency calculated."

**Precision:** Arrow included 4 low-relevance results (`_filename_match_boost`, `SearchResult` dataclass, `search_fts`, `config.load()`) that do not directly answer the query. The test files were partially useful but not essential.

**Natural language sensitivity:** The verbose natural-language query returned 0 results, suggesting BM25/vector fusion struggles with longer conversational queries. The reformulated keyword query worked well.

**Winner:** Traditional — the quality gap is significant here since Arrow missed the core calculation formula, which is the most important part of the answer.
