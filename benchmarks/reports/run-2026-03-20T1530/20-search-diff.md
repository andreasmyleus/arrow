# Query 20: What functions changed in search.py and who calls them?

**Category:** get_diff_context — Changed code analysis

## Precondition Note

No uncommitted changes existed in `src/arrow/search.py` at runtime (`git status` showed clean). Both approaches were run against the current state; the traditional approach used the most recent substantive commit (`9db1553`) diff to demonstrate the workflow, while Arrow's `get_diff_context` auto-detected no working-tree diff and returned dependency information only.

---

## Round 1 — Traditional (Glob, Grep, Read, Bash)

| Metric | Value |
|---|---|
| **Start** | 1774007871057 |
| **End** | 1774007891144 |
| **Duration** | 20,087 ms |
| **Tool calls** | 7 (3x Bash for git diff/status/log, 2x Grep for callers, 1x Bash timestamp start, 1x Bash timestamp end) |
| **Quality** | 5/5 |
| **Precision** | 95% |

### Findings (Traditional)

**Changed functions** (from commit `9db1553`):
1. `_extract_query_concepts()` — new helper, extracts meaningful terms from query
2. `_filename_match_boost()` — new helper, scores filename relevance to query concepts
3. `reciprocal_rank_fusion()` — `k` parameter changed from 60 to 20
4. `HybridSearcher.search()` — major refactor of scoring adjustments (BM25 bonus, filename boost, concept extraction replacing raw query terms)

**Callers identified:**
- `_extract_query_concepts`: called by `HybridSearcher.search()` in `search.py:509`; tested in `tests/test_core.py`
- `_filename_match_boost`: called by `HybridSearcher.search()` in `search.py:552`; tested in `tests/test_core.py`
- `reciprocal_rank_fusion`: called by `HybridSearcher.search()` in `search.py:460`; tested in `tests/test_core.py`, `tests/test_precision.py`
- `HybridSearcher.search()`: called by `server.py:491`, `cli.py:192`, and internally at `search.py:695`

---

## Round 2 — Arrow (`get_diff_context`)

| Metric | Value |
|---|---|
| **Start** | 1774007894290 |
| **End** | 1774007899719 |
| **Duration** | 5,429 ms |
| **Tool calls** | 1 |
| **Quality** | 2/5 |
| **Precision** | 40% |

### Findings (Arrow)

With no uncommitted changes, `get_diff_context` returned only a list of 13 dependent files (no changed functions, no callers, no diff hunks). It correctly identified the dependency graph but could not answer "what functions changed" since there was no working-tree diff to analyze.

**Dependent files returned:** `server.py`, `cli.py`, `vector_store.py`, plus 10 test/benchmark files.

---

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| **Duration** | 20,087 ms | 5,429 ms |
| **Tool calls** | 7 | 1 |
| **Changed functions identified** | 4 (full detail) | 0 (no diff detected) |
| **Callers identified** | All callers with line numbers | 13 dependent files (no caller detail) |
| **Quality** | 5/5 | 2/5 |
| **Precision** | 95% | 40% |

### Analysis

- **Speed:** Arrow was ~3.7x faster (5.4s vs 20.1s).
- **Completeness:** Traditional approach was significantly more complete because it could be directed to analyze a specific commit diff (`git diff 9db1553^..9db1553`). Arrow's `get_diff_context` only examines uncommitted working-tree changes, so with a clean tree it had nothing to diff.
- **Caller detail:** Traditional grep found exact callers with line numbers. Arrow returned a broad dependency list (13 files) without distinguishing which functions call which.
- **Limitation exposed:** `get_diff_context` would benefit from an optional `ref` parameter to analyze committed diffs, not just working-tree changes. When the tree is clean, the tool provides limited value for answering "what changed" questions.
- **When Arrow excels:** If there _were_ uncommitted changes, Arrow would likely provide a much faster and more structured answer in a single call. The tool is designed for active development workflows, not historical analysis.
