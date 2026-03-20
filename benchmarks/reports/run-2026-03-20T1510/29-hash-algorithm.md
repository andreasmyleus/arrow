# Query 29: What hash algorithm is used for content dedup and why?

**Category:** get_context — Needle
**Arrow tool under test:** get_context
**Timestamp:** 2026-03-20T15:10

## Answer

Arrow uses **xxHash3-128** (via the `xxhash` Python library) for content deduplication during incremental indexing.

- **Algorithm:** `xxhash.xxh3_128()` producing a 128-bit hex digest
- **Two entry points:** `hash_content(content)` for in-memory strings/bytes, `hash_file(path)` for on-disk files (streamed in 64KB chunks for memory efficiency)
- **Why xxHash3:** It is one of the fastest non-cryptographic hash algorithms available, optimized for throughput rather than collision resistance. Cryptographic guarantees are not needed here — the hash is only used to detect whether file content has changed since the last index. Speed matters because every file is hashed on every incremental indexing pass.
- **How it's used:** During `index_codebase`, each file is hashed and compared against the stored `content_hash` in the SQLite `files` table. If the hash matches, the file is skipped (`files_skipped` counter). This makes incremental re-indexing near-instant when nothing has changed. The same pattern is used in `index_remote_files`, `index_git_commit`, and `detect_stale_index`.

Key files: `src/arrow/hasher.py`, `src/arrow/indexer.py`, `src/arrow/storage.py`, `src/arrow/tools_data.py`.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| **Wall time** | 27,034 ms |
| **Tool calls** | 6 (1 Grep, 1 Glob, 2 Read, 2 Grep) |
| **Estimated tokens sent** | ~4,500 |
| **Estimated tokens received** | ~3,000 |
| **Quality** | 5/5 |
| **Precision** | 100% — all results directly relevant |

**Notes:** Found `hasher.py` quickly via Glob and Grep. The file is small (25 lines) so a single Read gave the complete picture. Follow-up Grep calls confirmed usage across indexer, storage, and tools_data. The "why" required inference from the algorithm choice (non-cryptographic, speed-optimized) and usage pattern (incremental skip logic).

## Round 2 — Arrow (get_context)

| Metric | Value |
|---|---|
| **Wall time** | 11,513 ms |
| **Tool calls** | 2 (first query returned no results, retry with keywords succeeded) |
| **Tokens returned** | ~4,875 (reported by tool) |
| **Chunks returned** | 17 |
| **Quality** | 4/5 |
| **Precision** | 45% — many chunks were from benchmarks, demo_comparison, tests, and export/import code that were tangentially related |

**Notes:** The natural-language query "What hash algorithm is used for content dedup and why?" returned **zero results** — a miss on the needle retrieval. A second attempt with explicit keywords (`xxhash hash_content hash_file content_hash incremental indexing dedup`) succeeded but returned substantial noise: benchmark code, demo scenarios, git commit indexing, export/import bundles, and test stubs. The core answer (hasher.py functions + indexer skip logic) was present but buried among 17 chunks. The traditional approach was more surgical — 6 tool calls but each returned precisely targeted information.

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| **Wall time** | 27.0s | 11.5s |
| **Tool calls** | 6 | 2 |
| **Precision** | 100% | ~45% |
| **Noise** | None | High (benchmarks, demos, tests) |
| **Found answer** | Yes | Yes (on retry) |
| **Required retry** | No | Yes — natural language query failed |

**Verdict:** Arrow was faster in wall time but required a retry after the natural-language query failed. The keyword-based retry succeeded but returned significant noise — less than half the chunks were directly relevant to the question. Traditional tools were slower but perfectly precise, finding the 25-line `hasher.py` file immediately and confirming its usage with targeted Grep. For this "needle" query about a specific implementation detail, the traditional approach delivered better signal-to-noise ratio. Arrow's failure on the natural-language form of this question is a notable weakness for a needle-type query.
