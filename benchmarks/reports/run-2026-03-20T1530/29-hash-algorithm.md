# Query 29: What hash algorithm is used for content dedup and why?

**Category:** Needle-in-Haystack
**Date:** 2026-03-20T15:30
**Codebase:** /Users/andreas/arrow

## Answer

The project uses **xxHash3-128** (via the `xxhash` Python library) for content deduplication during incremental indexing. The implementation lives in `src/arrow/hasher.py` which exposes two functions:

- `hash_content(content)` — hashes a string/bytes using `xxhash.xxh3_128()`, returns hex digest
- `hash_file(path)` — streams a file in 64KB chunks through `xxh3_128()` for memory efficiency

**Why xxHash3-128:**
- Extremely fast non-cryptographic hash (designed for speed, not security)
- 128-bit output provides sufficient collision resistance for content dedup
- Used to compare `content_hash` values in the `files` table to skip re-indexing unchanged files (incremental indexing)

The hash is stored in the SQLite `files` table as `content_hash TEXT` and compared on each index run — if the hash matches, the file is skipped.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| **Start** | 1774007909001 |
| **End** | 1774007918337 |
| **Duration** | 9,336 ms |
| **Tool calls** | 5 (1 Glob + 2 Grep + 1 Read + 1 timestamp) |
| **Files examined** | 6 files identified, 1 read fully, grep context across 6 |
| **Quality** | 5/5 |
| **Precision** | 98% |

**Notes:** Found the exact file immediately via Glob, confirmed usage across the codebase via Grep. Full picture of the algorithm, its purpose, and how it integrates with incremental indexing was clear from the results.

## Round 2 — Arrow (get_context only)

| Metric | Value |
|---|---|
| **Start** | 1774007921319 |
| **End** | 1774007924923 |
| **Duration** | 3,604 ms |
| **Tool calls** | 1 |
| **Chunks returned** | 0 |
| **Quality** | 1/5 |
| **Precision** | 0% |

**Notes:** `get_context` returned **no results** despite 78 files and 954 chunks being indexed. The query was natural-language and conceptual ("what hash algorithm and why"), which the relevance threshold filtering rejected entirely. This is a classic needle-in-haystack failure — the answer is concentrated in a single small file (`hasher.py`, 25 lines) that may not score highly enough on hybrid search for a conceptual question.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| **Duration** | 9,336 ms | 3,604 ms |
| **Tool calls** | 5 | 1 |
| **Quality** | 5/5 | 1/5 |
| **Precision** | 98% | 0% |
| **Answer found** | Yes | No |

## Verdict

**Traditional wins decisively.** Arrow returned zero results for this needle-in-haystack query. The traditional approach found the answer quickly via targeted file search (Glob for `hasher.py`) and keyword grep (`xxhash`). This highlights a weakness in relevance-threshold-based retrieval: small, highly specific files containing the exact answer may not score above the cutoff when the query is phrased conceptually. A keyword-targeted search strategy (Glob + Grep) is more reliable for "what specific thing is used" questions.
