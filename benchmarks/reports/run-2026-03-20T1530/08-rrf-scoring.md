# Benchmark 08 — RRF Scoring

**Query:** "What does reciprocal_rank_fusion do and how are BM25 and vector scores combined?"
**Category:** search_code — Hybrid search
**Date:** 2026-03-20

## Round 1 — Traditional Tools (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Start | 1774007816320 |
| End | 1774007823087 |
| Duration | 6767 ms |
| Tool calls | 4 (1 Grep for `reciprocal_rank_fusion`, 1 Grep for `rrf`, 1 Read `search.py`, 1 timestamp) |
| Files read | 1 (search.py — 785 lines, full file) |
| Tokens sent (est.) | ~5800 (full search.py) |
| Quality | 5/5 |
| Precision | 100% |

**Findings:** Full file read provided complete view of `reciprocal_rank_fusion` (lines 167-184), `HybridSearcher.search()` (lines 385-629), `filter_by_relevance` (lines 187-233), and all post-fusion adjustments (filename boost, BM25 bonus, test penalty, frecency). Everything needed was in a single file.

## Round 2 — Arrow (`search_code`)

| Metric | Value |
|---|---|
| Start | 1774007823087 |
| End | 1774007832840 |
| Duration | 9753 ms |
| Tool calls | 1 |
| Chunks returned | 10 |
| Tokens received (est.) | ~5200 |
| Quality | 5/5 |
| Precision | 80% |

**Top results by relevance:**

| # | Score | File | Chunk | Relevant? |
|---|---|---|---|---|
| 1 | 0.0545 | search.py:167-184 | `reciprocal_rank_fusion` | Yes — core function |
| 2 | 0.0522 | search.py:365-366 | `class HybridSearcher` | Yes — class docstring |
| 3 | 0.0429 | search.py:385-629 | `search()` method | Yes — full fusion pipeline |
| 4 | 0.0343 | storage.py:1064-1092 | `get_frecency_scores` | Yes — used in scoring |
| 5 | 0.0311 | test_core.py:569-579 | `test_rrf_k20_favors_top_ranks` | Yes — validates k=20 |
| 6 | 0.0279 | server.py:72-80 | `_get_vector_store` | Marginal |
| 7 | 0.0261 | cli.py:24-40 | `_get_components` | Marginal |
| 8 | 0.0255 | test_precision.py:140-144 | `test_zero_scores_handled` | No |
| 9 | 0.0250 | storage.py:720-753 | `search_fts` | Yes — BM25 search impl |
| 10 | 0.0247 | test_precision.py:122-126 | `test_uniform_scores_kept` | No |

**Relevant chunks:** 8/10 (results 1-5 and 9 directly relevant, 6-7 marginal context, 8 and 10 noise).

## Analysis

### Answer Completeness

Both rounds provided a complete answer:

1. **`reciprocal_rank_fusion`** takes multiple ranked lists (BM25 + vector), iterates each list, and accumulates `1/(k + rank + 1)` per item. Uses k=20 (lower than standard k=60) to give more weight to top-ranked items.

2. **BM25 scores** come from SQLite FTS5 (`search_fts`), negated for descending order.

3. **Vector scores** come from ONNX Jina embeddings via usearch, converted from distance to similarity (`1.0 - dist`).

4. **Post-fusion adjustments:** filename match boost (1.5x-2.0x), BM25 exact-match bonus (1.2x), non-code penalty, test file penalty (0.7x), frecency boost (up to 1.3x), conversation-aware dedup penalty (0.5x).

5. **Relevance filtering** via `filter_by_relevance`: drops results below 40% of top score or at a 50% score cliff.

### Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Duration | 6767 ms | 9753 ms |
| Tool calls | 4 | 1 |
| Precision | 100% | 80% |
| Quality | 5/5 | 5/5 |
| Tokens sent | ~5800 | ~5200 |
| Effort | Grep to locate, Read full file | Single query |

### Verdict

**Traditional wins on speed and precision** for this query. The entire answer lives in a single file (`search.py`), so Grep + Read was direct and fast — two targeted searches pinpointed the file, one Read retrieved everything. Arrow returned the same core content but was slower (9.8s vs 6.8s) and included 2 irrelevant chunks from test files. Arrow's advantage — single tool call vs 4 — is real but did not translate to time savings here. For single-file answers, traditional tools' directness is hard to beat.

**Winner: Traditional** (faster, higher precision, same quality)
