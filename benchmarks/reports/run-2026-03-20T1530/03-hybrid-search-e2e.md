# Query 3: Hybrid Search End-to-End Walkthrough

**Query:** "How does the hybrid search work end-to-end? Walk me through a query from get_context() to returned chunks."

**Type:** Broad architecture trace across multiple modules

---

## Round 1 — Traditional Tools (Glob, Grep, Read)

**Timestamps:** 1774007791296 - 1774007838096
**Duration:** 46,800 ms (~47s)

### Tool Calls
| # | Tool | Target | Lines Read |
|---|------|--------|------------|
| 1 | Grep | `src/arrow/` — `def get_context` | ~10 |
| 2 | Grep | `src/arrow/` — `def search_code` | ~10 |
| 3 | Grep | `src/arrow/` — `def hybrid_search` (no match) | 0 |
| 4 | Glob | `src/arrow/*.py` | — |
| 5 | Read | `server.py:760-860` (get_context MCP tool) | 100 |
| 6 | Read | `server.py:460-560` (search_code MCP tool) | 100 |
| 7 | Read | `search.py:1-80` (imports, constants, helpers) | 80 |
| 8 | Read | `search.py:80-180` (query concepts, filename boost, RRF) | 100 |
| 9 | Read | `search.py:180-330` (filter_by_relevance, classify_query) | 150 |
| 10 | Read | `search.py:330-480` (HybridSearcher.search — BM25 + vector) | 150 |
| 11 | Read | `search.py:480-680` (scoring adjustments, estimate_budget) | 200 |
| 12 | Read | `search.py:680-785` (get_context — relevance filtering, assembly) | 120 |
| 13 | Grep | `storage.py` — `def search_fts` | ~5 |
| 14 | Grep | `vector_store.py` — `def search` | ~5 |
| 15 | Grep | `embedder.py` — `def embed_query` | ~5 |
| 16 | Read | `storage.py:720-780` (search_fts BM25 via FTS5) | 60 |
| 17 | Read | `vector_store.py:1-85` (usearch vector index) | 85 |
| 18 | Read | `embedder.py:218-235` (embed_query) | 17 |

**Total tool calls:** 18
**Total lines read:** ~1,197
**Estimated tokens:** ~4,788 tokens (1,197 lines x 4 tok/line)
**Files touched:** 5 (server.py, search.py, storage.py, vector_store.py, embedder.py)

### Answer

The hybrid search flows through these stages:

1. **MCP Entry Point** (`server.py:get_context`):
   - Validates query, resolves project ID
   - Gets `HybridSearcher` singleton
   - If `token_budget=0` (auto), calls `searcher.estimate_budget()` which classifies the query as "targeted" vs "broad" and sets a ceiling (1000-8000 tokens) and search limit (5-30 results)
   - Loads session dedup state (sent chunk IDs) from storage
   - Calls `searcher.get_context()` with all parameters

2. **HybridSearcher.get_context** (`search.py:668`):
   - Delegates to `self.search()` to get ranked `SearchResult` objects
   - Applies a **second relevance pass**: drops results below 40% of top score (`_MIN_SCORE_RATIO`) or where score drops >50% vs previous result (`_SCORE_DROP_RATIO`)
   - Assembles output respecting token ceiling (hard stop, no truncation) and max 3 chunks per file
   - Returns dict with `query`, `token_budget`, `tokens_used`, `chunks_searched`, `chunks_returned`, `chunks`

3. **HybridSearcher.search** (`search.py:385`):
   - **BM25 leg:** `storage.search_fts(query)` — SQLite FTS5 with `bm25()` scoring, OR-joins query words, optional project_id filter. Returns `(chunk_id, bm25_score)` pairs.
   - **Vector leg:** `embedder.embed_query(query)` produces 768-dim vector via ONNX Jina model, then `vector_store.search(query_vec)` does ANN search using usearch (cosine metric, F16 precision). Over-fetches 3x for project filtering. Converts distances to similarity: `1.0 - dist`.
   - **Reciprocal Rank Fusion:** `reciprocal_rank_fusion()` with k=20 (sharper than standard k=60) combines both ranked lists: `score += 1/(k + rank + 1)` per list
   - **Dedup:** "penalize" strategy multiplies already-sent chunk scores by 0.5; "exclude" removes them entirely
   - **Frecency boost:** up to 30% boost for recently accessed files
   - **Scoring adjustments:** filename match boost (1.0-2.0x), BM25 exact-match bonus (1.2x), non-code penalty (0.6x default), test file penalty (0.7x unless query mentions tests), doc file boost (2.5x if doc query)
   - **Precision filtering:** `filter_by_relevance()` — drops tail below 40% of top score or at >50% score drop-off cliffs
   - **Materialization:** batch-fetches chunks and files from SQLite to build `SearchResult` objects with decompressed content

4. **Back in server.py:**
   - Records file access for frecency tracking
   - Records sent chunk IDs for session dedup
   - Logs analytics
   - Formats and returns JSON

**Quality: 5/5** — Complete end-to-end trace with all scoring parameters, thresholds, and data flow across all 5 modules.
**Precision: 95%** — Full coverage of the search pipeline. Only minor omissions: exact embedder internals and FTS5 table schema setup.

---

## Round 2 — Arrow (`get_context`)

**Timestamps:** 1774007840500 - 1774007849607
**Duration:** 9,107 ms (~9s)

### Tool Calls
| # | Tool | Result |
|---|------|--------|
| 1 | `get_context` | "No results" — zero chunks returned |

**Total tool calls:** 1
**Tokens returned:** ~50 (error message only)
**Chunks returned:** 0

### Answer

No answer could be produced. The query "How does the hybrid search work end-to-end? Walk me through a query from get_context() to returned chunks." returned zero results. The natural-language, broad architectural question did not match any indexed chunks with sufficient relevance scores.

**Quality: 0/5** — No useful content returned.
**Precision: 0%** — Complete failure to retrieve relevant code.

---

## Metrics Summary

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 46.8s | 9.1s |
| Tool calls | 18 | 1 |
| Lines/tokens read | ~1,197 lines / ~4,788 tok | 0 chunks / ~50 tok |
| Files touched | 5 | 0 |
| Answer quality | 5/5 | 0/5 |
| Precision | 95% | 0% |
| Usable answer | Yes | No |

---

## Observations

**Winner: Traditional (decisively)**

1. **Arrow completely failed this query.** The broad, natural-language architectural question returned zero results. This is likely because:
   - The relevance filtering (`_MIN_SCORE_RATIO=0.4`, `_SCORE_DROP_RATIO=0.5`) is tuned for precision, which aggressively cuts results when no single chunk is a strong match for a multi-module walkthrough question.
   - The query classification would label this as "broad" (contains "how does", "walk me through", "end-to-end"), setting a generous budget — but the underlying search still needs individual chunks to score well, and no single chunk covers the full pipeline.
   - Ironically, this query asks about the very search mechanism that failed to answer it.

2. **Traditional tools excelled** because the human-in-the-loop approach could strategically trace the call chain: start at the MCP entry point, follow `searcher.get_context()` into `search.py`, then drill into each sub-component (storage FTS, vector store, embedder). Each Read call was targeted at exactly the right line range.

3. **This is the worst-case scenario for single-tool semantic search:** a broad question that requires reading 5+ files and understanding the flow between them. No single chunk contains "the answer" — the answer is the composition of many functions across modules. Arrow's per-chunk relevance model cannot capture cross-module architectural narratives.

4. **Potential improvement for Arrow:** A `get_context` query that returns zero results could fall back to broader search strategies (lower thresholds, or keyword-only BM25 with relaxed filtering). Alternatively, the query could be decomposed into targeted sub-queries ("HybridSearcher.search method", "reciprocal_rank_fusion", "search_fts", "VectorStore.search").
