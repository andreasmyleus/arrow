# Query 08 — RRF Scoring

**Category:** Hybrid search
**Query:** "What does `reciprocal_rank_fusion` do and how are BM25 and vector scores combined?"
**Arrow tool:** `search_code`

## Answer

`reciprocal_rank_fusion` merges multiple ranked result lists into a single ranking using the formula `score += 1/(k + rank + 1)` for each item across all lists. It uses k=20 (lower than the standard 60) to give more weight to top-ranked results. The full hybrid pipeline:

1. BM25 via FTS5 produces up to 50 candidates (scores negated so higher = better)
2. Vector search via ONNX Jina embeddings + usearch produces up to 50 candidates (distance converted to similarity: `1 - dist`)
3. Both ranked lists are fused via `reciprocal_rank_fusion(ranked_lists, k=20)`
4. Post-fusion adjustments: conversation-aware dedup (50% penalty), frecency boost (up to 30%), filename-match boost, BM25 exact-match bonus (20%), non-code/test-file penalties
5. `filter_by_relevance` trims the low-relevance tail using min-score-ratio and score-drop-off checks

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 21.8 s |
| Tool calls | 7 |
| Lines read | ~260 |
| Tokens (est.) | ~1,040 |
| Quality | 5/5 |
| Precision | 95% |

**Steps:** Grep for `reciprocal_rank_fusion` across repo (found in search.py + tests), grep for bm25/vector pattern, then 4 sequential Read calls to walk through the `reciprocal_rank_fusion` function, `filter_by_relevance`, and the full `search()` method pipeline.

## Round 2 — Arrow (`search_code`)

| Metric | Value |
|---|---|
| Wall time | 8.0 s |
| Tool calls | 1 |
| Chunks returned | 5 |
| Tokens (est.) | ~3,200 |
| Quality | 5/5 |
| Precision | 100% |

**Steps:** Single `search_code` call returned: (1) the `reciprocal_rank_fusion` function definition, (2) the `HybridSearcher` class docstring, (3) a test for RRF k=20 behavior, (4) the full `search()` method showing BM25 + vector combination and all post-fusion adjustments, (5) PLAN.md pipeline overview. All essential code in one call.

## Comparison

| Metric | Traditional | Arrow | Winner |
|---|---|---|---|
| Wall time | 21.8 s | 8.0 s | Arrow (2.7x faster) |
| Tool calls | 7 | 1 | Arrow (7x fewer) |
| Tokens consumed | ~1,040 | ~3,200 | Traditional (3x less) |
| Quality | 5/5 | 5/5 | Tie |
| Precision | 95% | 100% | Arrow |

## Notes

- Arrow returned the complete `search()` method (250 lines) in a single chunk, which is why token count is higher -- but this is actually beneficial since it provides full context without multiple sequential reads.
- Traditional required iterative reading to follow the code flow through the method, needing 4 Read calls to piece together the full picture.
- Arrow's result ordering was ideal: RRF function first, then class definition, then test, then the full search pipeline, then the high-level doc -- exactly the order you'd want to read them.
- Both approaches achieved full understanding; Arrow was significantly faster with fewer tool calls but used more tokens due to returning the complete search method.
