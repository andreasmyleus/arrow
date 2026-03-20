# Query 03: Hybrid Search End-to-End Flow

**Query:** "How does the hybrid search work end-to-end? Walk me through a query from `get_context()` to returned chunks."

## Round 1 — Traditional Tools (Glob / Grep / Read)

| Metric | Value |
|---|---|
| Start | 1774009852005 |
| End | 1774009906657 |
| Duration (ms) | 54652 |
| Tool calls | 11 |
| Lines read | ~635 |
| Est. tokens | ~2540 |
| Quality | 5 / 5 |
| Precision | 95% |

### Answer Summary

The end-to-end flow from `get_context()` to returned chunks:

1. **`server.py` `get_context()` MCP tool** (line 792): Validates input, resolves project, gets config. If `token_budget=0` (default), calls `searcher.estimate_budget()` which classifies the query as "targeted" or "broad" and sets a ceiling (4000 or 8000 tokens). Retrieves session dedup state (previously sent chunk IDs).

2. **`search.py` `Searcher.get_context()`** (line 693): Delegates to `self.search()` to get ranked candidates, then applies a second relevance pass:
   - Score floor: drops results < 25% of top score
   - Cliff detection: stops when score drops to < 40% of previous result
   - Per-file cap: max 3 chunks per file
   - Token ceiling: hard stop (no truncation)
   - Returns dict with chunks, tokens_used, budget metadata

3. **`search.py` `Searcher.search()`** (line 404): The hybrid search core:
   - **BM25 via FTS5**: `storage.search_fts()` tokenizes query with OR, runs SQLite FTS5 MATCH with `bm25()` scoring, returns `(chunk_id, score)` pairs
   - **Vector search**: `embedder.embed_query()` generates a Jina ONNX embedding (768-dim), then `vector_store.search()` does cosine-similarity nearest-neighbor search via usearch (F16 precision)
   - **Reciprocal Rank Fusion** (`reciprocal_rank_fusion()`, line 186): Merges BM25 and vector ranked lists using `score = sum(1/(k + rank + 1))` with k=20 for sharper top-rank differentiation
   - **Dedup**: Penalizes already-sent chunks by 50% (or excludes them)
   - **Frecency boost**: Up to 30% boost for recently accessed files
   - **Score adjustments**: Filename match boost (up to 2x), BM25 exact-match bonus (1.2x), non-code penalty, test file penalty (0.7x)
   - **`filter_by_relevance()`** (line 206): First-pass tail removal using same min-score-ratio and cliff-detection logic

4. **Result materialization** (line 595): Batch-fetches chunk records and file records from SQLite to avoid N+1 queries, decompresses content, builds `SearchResult` objects.

5. **Back in `server.py`**: Records sent chunks for session dedup, records frecency access, logs analytics, returns formatted JSON.

### Files examined
- `/Users/andreas/arrow/src/arrow/server.py` — MCP tool entry point, searcher instantiation
- `/Users/andreas/arrow/src/arrow/search.py` — HybridSearcher, RRF, relevance filtering, budget estimation
- `/Users/andreas/arrow/src/arrow/storage.py` — FTS5 BM25 search (`search_fts`)
- `/Users/andreas/arrow/src/arrow/vector_store.py` — usearch cosine similarity search
- `/Users/andreas/arrow/src/arrow/embedder.py` — Jina ONNX query embedding

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Start | 1774009910323 |
| End | 1774009920027 |
| Duration (ms) | 9704 |
| Tool calls | 1 |
| Tokens returned | 0 |
| Chunks returned | 0 |
| Quality | 1 / 5 |
| Precision | 0% |

### Notes

`get_context` returned **zero results** for this natural-language architectural query. The response was "No results" with suggestions to try broader keywords. This is a case where a broad exploratory/architectural question does not match well against code chunks via either BM25 keyword matching or semantic vector search. The query is long, conversational, and asks about a flow spanning multiple files — none of which would score highly as individual chunk matches.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Duration (ms) | 54652 | 9704 |
| Tool calls | 11 | 1 |
| Est. tokens | ~2540 | 0 |
| Quality | 5 / 5 | 1 / 5 |
| Precision | 95% | 0% |
| Useful answer | Yes — complete E2E trace | No — zero results |

### Verdict

**Traditional tools win decisively.** This architectural "trace the flow" question requires following call chains across 5 files and understanding how components connect. Traditional tools (Grep to find entry points, Read to follow the code) are ideal for this. Arrow's `get_context` failed entirely — broad natural-language queries about system architecture don't map well to individual code chunk retrieval. A multi-tool Arrow approach (e.g., `search_structure` + `resolve_symbol` + `trace_dependencies`) might have worked, but `get_context` alone could not answer this.
