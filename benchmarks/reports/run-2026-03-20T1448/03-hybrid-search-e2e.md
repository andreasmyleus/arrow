# Query 3: Hybrid Search End-to-End Flow

**Query:** "How does the hybrid search work end-to-end? Walk me through a query from `get_context()` to returned chunks."
**Category:** Architecture
**Arrow tool(s) under test:** `get_context`
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 32.9 s |
| Tool calls | 9 (3 Grep, 4 Read, 2 timestamp) |
| Lines read | ~510 |
| Est. tokens | ~2,040 |
| Quality | 5/5 |
| Precision | 95% |

### Answer (Traditional)

The end-to-end flow from `get_context()` to returned chunks:

1. **`server.py:get_context()`** (line 792) — MCP entry point. Validates input, resolves project ID, gets storage and searcher singletons. If `token_budget=0` (default), calls `searcher.estimate_budget()` which classifies the query (targeted vs broad) and sets a token ceiling and search limit. Fetches session dedup state (previously sent chunk IDs).

2. **`search.py:Searcher.get_context()`** (line 693) — Calls `self.search()` with the budget parameters. Iterates results, enforces a per-file cap of 3 chunks and the hard token ceiling. Assembles output dicts with file, project, name, kind, lines, content, tokens.

3. **`search.py:Searcher.search()`** (line 404) — The hybrid search core:
   - **BM25 leg:** Calls `storage.search_fts(query)` which runs SQLite FTS5 `MATCH` with `bm25()` scoring. Returns `(chunk_id, bm25_score)` pairs.
   - **Vector leg:** Calls `embedder.embed_query(query)` (ONNX Jina model) to get a query vector, then `vector_store.search(query_vec)` which runs usearch nearest-neighbor search. Returns `(chunk_id, distance)` pairs, converted to similarity as `1.0 - distance`.
   - **Fusion:** Both ranked lists fed into `reciprocal_rank_fusion()` (k=20) which sums `1/(k + rank + 1)` per item across lists.
   - **Dedup:** Already-sent chunks penalized by 0.5x (or excluded in legacy mode).
   - **Frecency boost:** Recently accessed files boosted up to 30%.
   - **Score adjustments:** File-name match boost, non-code penalty (markdown/config), BM25 exact-match bonus (1.2x), test file penalty (0.7x when query is not about tests).
   - **Relevance filtering:** `filter_by_relevance()` applies min-score-ratio floor and score-cliff detection, keeping at least `_MIN_RESULTS_FLOOR` results.
   - **Materialization:** Batch-fetches chunks and files from storage, decompresses content, builds `SearchResult` objects.

4. **Back in `server.py`** — Records sent chunks for session dedup, records file access for frecency, logs analytics.

### Key files traced
- `/Users/andreas/arrow/src/arrow/server.py` (lines 792-870)
- `/Users/andreas/arrow/src/arrow/search.py` (lines 186-203, 206-252, 404-652, 656-690, 693-784)
- `/Users/andreas/arrow/src/arrow/storage.py` (lines 720-750)
- `/Users/andreas/arrow/src/arrow/vector_store.py` (lines 61-75)
- `/Users/andreas/arrow/src/arrow/embedder.py` (lines 221-226)

---

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall time | 15.5 s |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens used | 0 |
| Quality | 0/5 |
| Precision | 0% |

### Result

`get_context` returned **zero results** for this natural-language architectural query. The response was:

> No results for: How does the hybrid search work end-to-end? Walk me through a query from get_context() to returned chunks.

This is a complete miss. The query is a broad architectural question spanning multiple files and functions. The hybrid search apparently could not match this prose-style question to the relevant code chunks in `search.py`, `server.py`, `storage.py`, `vector_store.py`, and `embedder.py`.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 32.9 s | 15.5 s |
| Tool calls | 9 | 1 |
| Tokens consumed | ~2,040 | ~0 |
| Quality | 5/5 | 0/5 |
| Precision | 95% | 0% |
| Completeness | Full e2e trace across 5 files | No results |

### Verdict

**Traditional wins decisively.** Arrow returned zero results for this architectural walkthrough query. While Arrow was faster in wall-clock time, it provided no useful information whatsoever. The traditional approach successfully traced the complete flow across 5 files, identifying every stage from MCP entry point through BM25 + vector search, RRF fusion, score adjustments, relevance filtering, and result materialization.

This exposes a significant weakness: broad natural-language architectural queries that span multiple files and don't contain obvious code keywords may fail to match any indexed chunks. The query phrasing ("how does hybrid search work end-to-end") is semantically rich but may not have enough lexical overlap with function/variable names for BM25, and the vector embeddings may not bridge the gap either. Possible causes:

1. **BM25 miss** — the prose query terms ("end-to-end", "walk me through") have no FTS5 matches in code chunks.
2. **Vector search miss or low scores** — the semantic embedding of this question may not be close enough to code chunk embeddings.
3. **Over-aggressive relevance filtering** — even if some results were found, `filter_by_relevance()` may have discarded them as below the score floor.

A keyword-focused query like `"hybrid_search BM25 vector reciprocal_rank_fusion"` would likely have succeeded. This suggests `get_context` works best with code-oriented queries rather than prose architectural questions.
