# Query 26: Dead Code Detection

**Query:** "Are there any unused functions or dead code in this project?"
**Category:** Dead code
**Arrow tool(s) under test:** `find_dead_code`
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 82,871 ms |
| Tool calls | 14 |
| Lines read | ~320 |
| Tokens (est.) | ~1,280 |
| Quality | 3/5 |
| Precision | 70% |

### Approach
1. Listed all Python source files with Glob.
2. Extracted all function definitions via Grep across `src/arrow/*.py`.
3. For each suspicious function name, ran Grep across `src/arrow/` and `tests/` to check for callers.
4. Iteratively narrowed down candidates by checking import statements, test usage, and framework callbacks.

### Findings
Confirmed dead (no callers in src or tests):
- `storage.get_session_chunks_detail` -- defined but never referenced anywhere
- `storage.get_project_meta` -- defined but never called
- `storage.get_index_staleness` -- defined but never called

Possibly dead (only in tests, not production code):
- `git_utils.has_new_commits` -- only referenced in test_git_utils.py, not in production code

### Limitations
- Manual approach is exhaustive but very slow; checking each function individually requires many tool calls.
- Hard to systematically cover all ~130+ functions without missing some.
- Cannot easily distinguish framework callbacks (watchdog handlers, pytest fixtures) from truly dead code.
- Did not check for dynamic dispatch (`getattr`, string-based references).

---

## Round 2 — Arrow (`find_dead_code`)

| Metric | Value |
|---|---|
| Wall time | 12,441 ms |
| Tool calls | 1 |
| Chunks returned | 6 results |
| Tokens (est.) | ~250 |
| Quality | 4/5 |
| Precision | 50% |

### Findings
Arrow returned 6 dead code candidates:

| Function | File | Verdict |
|---|---|---|
| `get_project_meta` | storage.py:872 | TRUE positive -- no callers anywhere |
| `get_session_chunks_detail` | storage.py:1196 | TRUE positive -- no callers anywhere |
| `get_index_staleness` | storage.py:1377 | TRUE positive -- no callers anywhere |
| `on_modified` | watcher.py:35 | FALSE positive -- watchdog framework callback |
| `on_deleted` | watcher.py:43 | FALSE positive -- watchdog framework callback |
| `clean_server_state` | conftest.py:82 | FALSE positive -- autouse pytest fixture |

3 true positives, 3 false positives (50% precision). The false positives are all framework-invoked methods (watchdog event handlers, pytest fixtures) that are called implicitly rather than by direct reference.

### What Arrow missed
- `has_new_commits` in git_utils.py (used in tests only, not in production code -- debatable whether this counts as dead)
- The `count_tokens` duplication between search.py and indexer.py (not exactly dead code, but a code smell)

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 82,871 ms | 12,441 ms |
| Speedup | 1x | **6.7x** |
| Tool calls | 14 | 1 |
| Tokens est. | ~1,280 | ~250 |
| Quality | 3/5 | 4/5 |
| Precision | 70% | 50% |
| True positives found | 2 | 3 |

### Analysis
Arrow is dramatically faster (6.7x) and requires only a single tool call. It found one more true positive (`get_index_staleness`) that the traditional approach missed due to incomplete manual scanning. However, Arrow's precision is lower at 50% due to framework callback false positives (watchdog handlers, pytest fixtures). The traditional approach had better precision because the human-in-the-loop verification naturally filters out framework-invoked methods, but was much slower and less comprehensive in coverage.

Arrow's main weakness here is that it cannot distinguish methods that are called by frameworks (watchdog event dispatch, pytest dependency injection) from genuinely unreferenced code. This is a known limitation of static analysis without framework-specific heuristics.

**Winner: Arrow** -- the speed advantage and superior recall outweigh the false positive rate, which a developer can quickly triage.
