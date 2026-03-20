# Query 08 — RRF Scoring

**Query:** "What does reciprocal_rank_fusion do and how are BM25 and vector scores combined?"
**Category:** search_code — Hybrid search
**Arrow tool under test:** `search_code`

---

## Expected Answer

The `reciprocal_rank_fusion` function in `src/arrow/search.py` combines multiple ranked lists (BM25 and vector search results) using the RRF formula: `score(item) += 1/(k + rank + 1)` for each list the item appears in, with `k=20` (lower than the standard 60) to give more weight to top-ranked results. BM25 results come from SQLite FTS5 full-text search; vector results come from embedding the query and searching the usearch vector index. Both lists are collected into `ranked_lists`, fused via RRF, then post-processed with dedup penalties, frecency boost, file-name boost, BM25 exact-match bonus (20%), test file penalty, non-code penalty, and finally relevance tail filtering.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 21,172 ms |
| Tool calls | 7 (2 Grep, 5 Read) |
| Estimated tokens | ~4,500 |
| Quality | 5/5 |
| Precision | 100% |

### Process
1. Grepped for `reciprocal_rank_fusion` and `def.*rrf` across `src/` — found `search.py`.
2. Read the `reciprocal_rank_fusion` function (lines 186-203) and `filter_by_relevance` (lines 206-245).
3. Read the `search()` method (lines 400-540) to see BM25 collection, vector collection, RRF call, and all post-processing steps.

### Findings
- Found the complete RRF implementation and the full `search()` pipeline.
- All relevant code was in a single file (`search.py`), making traditional search efficient.

---

## Round 2 — Arrow (`search_code`)

| Metric | Value |
|---|---|
| Wall time | 14,335 ms |
| Tool calls | 2 (first returned 0 results, second returned 5) |
| Chunks returned | 5 |
| Quality | 5/5 |
| Precision | 100% |

### Process
1. First query (natural language) returned 0 results — likely too long/unstructured for BM25 matching.
2. Second query with keywords `reciprocal_rank_fusion BM25 vector scores combined` returned 5 results with all relevant code.

### Results returned
1. `search.py:186-203` — `reciprocal_rank_fusion` function (score 0.0545)
2. `search.py:384-385` — `HybridSearcher` class docstring (score 0.0522)
3. `search.py:404-654` — Full `search()` method (score 0.0429)
4. `storage.py:1087-1115` — `get_frecency_scores` (score 0.0343)
5. `tests/test_core.py:569-579` — RRF test (score 0.0311)

### Notes
- The natural language query format failed completely (0 results). Keyword-style queries work better.
- The full `search()` method was returned as a single large chunk (250 lines), which is comprehensive but token-heavy.
- Result 4 (`get_frecency_scores`) and result 5 (test) are related but not core to the question — mild noise.
- Result 3 alone contained all the information needed, but at ~250 lines it used significant tokens.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 21,172 ms | 14,335 ms |
| Tool calls | 7 | 2 |
| Tokens (est.) | ~4,500 | ~6,500 |
| Quality | 5/5 | 5/5 |
| Precision | 100% | 60% (3/5 results directly relevant) |

### Verdict

**Arrow wins on speed and tool calls** but is slightly less token-efficient due to the large `search()` method chunk and two bonus results that are tangential. The initial natural language query returning 0 results is a notable UX issue — users must use keyword-style queries for reliable results. Both approaches achieve perfect quality since the answer is concentrated in a single file. Arrow's advantage would be larger if the relevant code were spread across multiple files.

### Suggestions
- The natural language query returning 0 results suggests the BM25 indexing may struggle with longer question-style queries. Consider query preprocessing (stop-word removal, extracting key terms from natural language questions).
