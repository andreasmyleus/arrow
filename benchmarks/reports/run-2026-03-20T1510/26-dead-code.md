# Query 26: Dead Code Detection

**Query:** "Are there any unused functions or dead code in this project?"
**Category:** find_dead_code -- Dead code
**Arrow tool under test:** `find_dead_code`
**Date:** 2026-03-20

---

## Round 1 -- Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Start | 1774012386800 |
| End | 1774012474453 |
| Duration | 87.7s |
| Tool calls | 22 (2 Glob, 18 Grep, 1 Read, 1 Bash) |
| Estimated tokens | ~18,000 |
| Quality | 4/5 |
| Precision | 85% |

### Method

1. Glob to list all source files in `src/arrow/`.
2. Two broad Grep calls to extract all top-level function defs and all method defs.
3. Systematic Grep calls for each candidate function name to check if it is referenced outside its definition -- 18 targeted searches covering ~30 functions.

### Findings

**Truly dead (zero callers in production or test code):**
- `get_session_chunks_detail` in `storage.py:1196` -- never called anywhere in source or tests.
- `get_index_staleness` in `storage.py:1377` -- never called; `detect_stale_index` in tools_data.py implements its own hash-based check instead.

**Test-only (no production callers, but exercised by tests):**
- `has_new_commits` in `git_utils.py:99` -- only referenced in `tests/test_git_utils.py`.
- `clear_session` in `storage.py:1212` -- only referenced in `tests/test_conversation.py`.
- `get_project_meta` in `storage.py:872` -- only referenced in `tests/test_core.py`.
- `set_project_meta` in `storage.py:868` -- only referenced in `tests/test_core.py`.

**Duplicate definition:**
- `count_tokens` in `search.py:170` -- defined but never called within search.py or imported from it. A separate `count_tokens` in `indexer.py:36` is the one actually used. The search.py version is dead.

### Limitations

With ~170 functions/methods across 16 source files, only ~30 were checked in detail due to the serial nature of Grep-based analysis. The approach was biased toward functions that "looked" potentially unused (utility helpers, internal methods). Some dead code in less-obvious places may have been missed.

---

## Round 2 -- Arrow (`find_dead_code`)

| Metric | Value |
|---|---|
| Start | 1774012477642 |
| End | 1774012491059 |
| Duration | 13.4s |
| Tool calls | 1 |
| Estimated tokens | ~500 |
| Quality | 3/5 |
| Precision | 100% |

### Findings

Arrow returned 3 dead functions:

| Function | File | Lines |
|---|---|---|
| `get_project_meta` | `src/arrow/storage.py` | 872-880 |
| `get_session_chunks_detail` | `src/arrow/storage.py` | 1196-1210 |
| `get_index_staleness` | `src/arrow/storage.py` | 1377-1399 |

All three are true positives -- verified via Grep that none have callers in production code. `get_project_meta` has a test caller but no production usage.

### What Arrow missed

- `count_tokens` in `search.py` (duplicate, never called) -- not detected.
- `set_project_meta` in `storage.py` (test-only, no production callers) -- not detected.
- `has_new_commits` in `git_utils.py` (test-only, no production callers) -- not detected.
- `clear_session` in `storage.py` (test-only, no production callers) -- not detected.

The tool's filtering logic (skipping private functions, test helpers, entry points) means it intentionally excludes some categories. Functions that have test callers but no production callers are not flagged, which is a reasonable design choice but limits recall for a broader "dead code" question.

---

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Duration | 87.7s | 13.4s |
| Tool calls | 22 | 1 |
| Tokens (est.) | ~18,000 | ~500 |
| True positives | 7 (2 truly dead + 4 test-only + 1 duplicate) | 3 (all true) |
| False positives | 0 | 0 |
| Precision | 100% | 100% |
| Recall | Higher (more categories) | Lower (production-dead only) |
| Quality | 4/5 | 3/5 |

### Analysis

**Speed:** Arrow is 6.5x faster (13s vs 88s) and uses ~36x fewer tokens.

**Accuracy:** Both approaches have 100% precision (no false positives). Traditional found more dead code overall (7 items vs 3), but Arrow's results are a strict subset focused on the most clearly dead functions. Arrow missed the `count_tokens` duplicate in search.py and the test-only functions, but its 3 results are all high-confidence findings.

**Completeness:** Traditional analysis is fundamentally limited too -- checking all ~170 functions would require 170+ Grep calls. The 22-call approach sampled about 30 functions. Arrow scans all indexed symbols systematically via its LIKE-based reference check, but its filtering heuristics exclude some valid dead code (test-only callers, duplicates).

**Winner:** Arrow wins on efficiency. Traditional wins on recall for a thorough audit. For a quick "any dead code?" question, Arrow's single-call approach is clearly superior. For a comprehensive cleanup effort, traditional analysis with targeted verification is more thorough.
