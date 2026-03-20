# Query 29: What hash algorithm is used for content dedup and why?

**Category:** Needle-in-haystack
**Run:** 2026-03-20T1815

## Question
"What hash algorithm is used for content dedup and why?"

## Answer
Arrow uses **xxHash3-128** (via the `xxhash` Python library, `>=3.4.0`) for content deduplication during incremental indexing. The `hasher.py` module provides two functions: `hash_content()` for in-memory strings/bytes and `hash_file()` for on-disk files (read in 64KB chunks). Content hashes are stored in the `files.content_hash` column and compared on re-index — if the hash matches, the file is skipped. xxHash3 was chosen for its extreme speed (non-cryptographic), which matters when hashing potentially thousands of source files during indexing.

## Round 1 — Traditional Tools

| Metric | Value |
|---|---|
| Tool calls | 5 |
| Files examined | 4 (hasher.py, indexer.py, storage.py, pyproject.toml) |
| Lines read | ~85 |
| Estimated tokens | ~340 |
| Wall time (ms) | 12854 |
| Quality | 5/5 |
| Precision | 95% |

**Method:** Read `hasher.py` directly (25 lines, complete file), then grepped for hash usage in indexer.py and storage.py to understand how content hashes drive deduplication, and checked pyproject.toml for the dependency version.

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Wall time (ms) | 13249 |
| Quality | 1/5 |
| Precision | 0% |

**Method:** Single `get_context` call with the natural language query. Returned no results despite the codebase having 114 files and 1231 chunks indexed.

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Tool calls | 5 | 1 |
| Tokens consumed | ~340 | 0 |
| Wall time (ms) | 12854 | 13249 |
| Quality | 5/5 | 1/5 |
| Precision | 95% | 0% |
| Winner | **Traditional** | |

## Notes

- Arrow completely failed this query — `get_context` returned zero results for a natural language question about hash algorithms. The relevance threshold likely filtered out all chunks since the query terms ("hash algorithm", "content dedup") may not have matched well against the code-centric embeddings/BM25 index.
- Traditional tools found the answer quickly: `hasher.py` is a small, self-contained 25-line module that fully answers the question. A single Read + targeted Grep was sufficient.
- This is a case where the needle (a small utility module) is easy to find with direct file access but hard to surface via semantic search when the query uses conceptual terms not present in the code.
