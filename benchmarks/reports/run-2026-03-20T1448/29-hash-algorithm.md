# Query 29 — What hash algorithm is used for content dedup and why?

**Category:** Needle
**Arrow tool(s) under test:** `get_context`

## Answer

Arrow uses **xxHash3-128** (via the `xxhash` Python package, `>=3.4.0`) for content deduplication during incremental indexing. The implementation lives in `src/arrow/hasher.py`, which exposes two functions:

- `hash_content(content)` — hashes a string/bytes value in one shot using `xxhash.xxh3_128().hexdigest()`.
- `hash_file(path)` — hashes a file in streaming 64 KB chunks for memory efficiency.

**Why xxHash3-128?** xxHash3 is an extremely fast non-cryptographic hash function. For incremental indexing, the only requirement is collision resistance sufficient to detect file changes — cryptographic security is unnecessary. xxHash3-128 provides:
- Very high throughput (faster than SHA-256 or MD5 by an order of magnitude).
- 128-bit output providing negligible collision probability for dedup purposes.
- Streaming API for large files without loading them entirely into memory.

**How it's used for dedup:** During indexing (`indexer.py`), each file is hashed before processing. The hash is compared against the stored `content_hash` in the `files` table (`storage.py`). If hashes match, the file is skipped (`files_skipped` counter increments). This makes re-indexing fast — only changed files are reprocessed. The same mechanism is used in `detect_stale_index` (`tools_data.py`) to identify files that have changed on disk since last indexing.

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 21,665 ms |
| Tool calls | 7 (1 Glob, 3 Grep, 2 Read, 1 Bash/grep) |
| Lines read | ~115 |
| Tokens (est.) | ~460 |
| Quality | 5/5 — found hasher.py immediately, traced all usage sites, confirmed dependency version |
| Precision | 95% — all content directly relevant to the question |

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|--------|-------|
| Wall time | 7,709 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Quality | 1/5 — returned no results at all |
| Precision | 0% — no content returned |

## Comparison

| Dimension | Traditional | Arrow | Winner |
|-----------|------------|-------|--------|
| Speed | 21.7s | 7.7s | Arrow |
| Accuracy | Complete answer | No results | Traditional |
| Token efficiency | ~460 tokens | 0 tokens | Traditional |
| Tool calls | 7 | 1 | Arrow |

**Winner: Traditional**

## Notes

- Arrow returned zero results for this query despite the codebase containing a clear, small, dedicated `hasher.py` module. The query's natural-language phrasing ("what hash algorithm is used for content dedup and why") likely didn't match the BM25 or vector representations of the `hasher.py` chunk, which uses technical terms like "xxHash3-128" and "incremental indexing" rather than "content dedup."
- This is a classic needle-in-a-haystack query where the answer lives in a single small file. Traditional tools found it instantly via filename (`hasher.py`) and targeted grep for `xxhash`.
- A more keyword-oriented query like "xxhash content_hash" would likely have succeeded with Arrow. The failure highlights a gap in handling conceptual/why questions that map to specific implementation files.
