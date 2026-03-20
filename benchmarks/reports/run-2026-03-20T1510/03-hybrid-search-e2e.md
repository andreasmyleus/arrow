# Query 03: Hybrid Search End-to-End Flow

**Query:** "How does the hybrid search work end-to-end? Walk me through a query from `get_context()` to returned chunks."

## Round 1 — Traditional Tools (Glob / Grep / Read)

| Metric | Value |
|---|---|
| Start | 1774012283054 |
| End | 1774012313059 |
| Duration (ms) | 30005 |
| Tool calls | 10 |
| Lines read | ~520 |
| Est. tokens | ~2080 |
| Quality | 5 / 5 |
| Precision | 95% |

### Answer Summary

The end-to-end flow from `get_context()` to returned chunks:

1. **`server.py` `get_context()` MCP tool** (line 801): Validates input, resolves project, gets storage/searcher. If `token_budget=0` (default), calls `searcher.estimate_budget()` which classifies the query as "targeted" or "broad" and sets a ceiling (4000 or 8000 tokens). Retrieves session dedup state (previously sent chunk IDs) and session token total.

2. **`search.py` `Searcher.search()`** (line 404): The hybrid search core:
   - **BM25 via FTS5**: `storage.search_fts()` tokenizes query words with OR, runs SQLite FTS5 MATCH with `bm25()` scoring, returns `(chunk_id, score)` pairs
   - **Vector search**: `embedder.embed_query()` generates a Jina ONNX embedding, then `vector_store.search()` does cosine-similarity nearest-neighbor search via usearch
   - **Reciprocal Rank Fusion** (`reciprocal_rank_fusion()`, line 186): Merges BM25 and vector ranked lists using `score = sum(1/(k + rank + 1))` with k=20 for sharper top-rank differentiation
   - **Conversation dedup**: Penalizes already-sent chunks by 50% (or excludes them based on strategy)
   - **Frecency boost**: Up to 30% boost for recently accessed files
   - **Score adjustments**: Filename match boost (via concept extraction), BM25 exact-match bonus (1.2x), non-code penalty, test file penalty (0.7x), doc query boost (2.5x)
   - **`filter_by_relevance()`** (line 206): Tail removal using min-score-ratio and cliff-detection logic

3. **Result materialization** (line 595): Batch-fetches chunk records and file records from SQLite to avoid N+1 queries, decompresses content (or uses content_text if available), builds `SearchResult` objects.

4. **`search.py` `Searcher.get_context()`** (line 693): Receives results from `search()`, trusts the relevance filtering already applied, then applies per-file cap (max 3 chunks per file) and token ceiling (hard stop, no truncation). Returns dict with chunks, tokens_used, budget metadata.

5. **Back in `server.py`** (line 870): Records file access for frecency, records sent chunks for session dedup, logs analytics, adds budget mode and session metadata, returns formatted JSON. If no results, returns helpful suggestions.

### Files examined
- `/Users/andreas/arrow/src/arrow/server.py` — MCP tool entry point, budget resolution, session tracking
- `/Users/andreas/arrow/src/arrow/search.py` — HybridSearcher, RRF, relevance filtering, budget estimation
- `/Users/andreas/arrow/src/arrow/storage.py` — FTS5 BM25 search (`search_fts`)
- `/Users/andreas/arrow/src/arrow/vector_store.py` — usearch cosine similarity search
- `/Users/andreas/arrow/src/arrow/embedder.py` — Jina ONNX query embedding

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Start | 1774012315802 |
| End | 1774012327119 |
| Duration (ms) | 11317 |
| Tool calls | 1 |
| Tokens returned | 0 |
| Chunks returned | 0 |
| Quality | 1 / 5 |
| Precision | 0% |

### Notes

`get_context` returned **zero results** for this natural-language architectural query. The response was "No results" with suggestions to try broader keywords. This is a broad, conversational question about a flow spanning multiple files and functions — individual code chunks do not match well against either BM25 keyword matching or semantic vector search for this type of query.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Duration (ms) | 30005 | 11317 |
| Tool calls | 10 | 1 |
| Est. tokens | ~2080 | 0 |
| Quality | 5 / 5 | 1 / 5 |
| Precision | 95% | 0% |
| Useful answer | Yes — complete E2E trace | No — zero results |

### Verdict

**Traditional tools win decisively.** This architectural "trace the flow" question requires following call chains across 5 files and understanding how components connect. Traditional tools (Grep to find entry points, Read to follow the code) are ideal for this kind of investigative work. Arrow's `get_context` failed entirely — broad natural-language questions about system architecture do not map well to individual code chunk retrieval. A multi-tool Arrow approach (e.g., `search_structure` to find `get_context` + `trace_dependencies` + `resolve_symbol`) might have succeeded, but `get_context` alone could not answer this.
