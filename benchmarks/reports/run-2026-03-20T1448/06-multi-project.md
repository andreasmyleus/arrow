# Query 6: Multi-Project Handling

**Query:** "How does Arrow handle multiple projects — indexing, searching, and isolation?"
**Category:** Cross-cutting
**Arrow tool(s) under test:** `get_context`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 25,588 ms |
| Tool calls | 9 (3 Grep, 4 Read, 2 Bash timestamp) |
| Lines read | ~480 |
| Estimated tokens | ~1,920 |
| Quality | 5/5 |
| Precision | 95% |

### Answer (Traditional)

Arrow handles multiple projects through a layered isolation model:

**Indexing:**
- `indexer._resolve_project()` finds or creates a project by matching `root_path` in the `projects` table. It auto-detects git info (name, remote, branch, commit) and calls `storage.create_project()` which uses `INSERT ... ON CONFLICT(name) DO UPDATE` (upsert semantics).
- Every `files` row and every `chunks` row carries a `project_id` foreign key with `ON DELETE CASCADE`, so deleting a project cascades to all its data.
- Indexes exist on `files(project_id)` and `chunks(project_id)` for fast scoped queries.

**Searching:**
- **BM25 (FTS5):** `storage.search_fts()` joins `chunks_fts` with `chunks` and adds `AND c.project_id = ?` when a project is specified.
- **Vector search:** The usearch vector index is *global* (single index file, no per-project partitioning). Project isolation is achieved via **post-filtering**: `search.py` over-fetches 3x candidates from the vector index, then filters by `chunk.project_id == project_id` before fusion.
- **Regex search:** `storage.search_regex()` pre-filters chunks by `WHERE project_id = ?` before applying the regex.

**Auto-detection / Isolation:**
- `server._detect_project_from_cwd()` walks up to the git root, matches it against indexed projects by `root_path`, and auto-scopes searches. This prevents cross-project contamination (e.g., returning pydantic results when working in arrow).
- `server._resolve_project_id()` returns a sentinel `_PROJECT_NOT_FOUND = -1` when a named project is not found, so callers never silently fall back to all-projects search.
- `_check_project_id()` returns a JSON error listing available projects.

**Lifecycle:**
- `remove_project()` stops the file watcher, removes the lock, and calls `storage.delete_project()` which cascades.
- Each local project gets its own watchdog file watcher (`_start_watcher(project_id, root)`), started at server boot via `_start_all_watchers()`.

### Files visited
- `src/arrow/storage.py` (schema, CRUD, FTS search, project table)
- `src/arrow/search.py` (hybrid search, vector post-filtering)
- `src/arrow/indexer.py` (`_resolve_project`)
- `src/arrow/server.py` (cwd detection, watcher lifecycle, resolve helpers)
- `src/arrow/vector_store.py` (global index, no per-project partitioning)
- `src/arrow/tools_data.py` (`remove_project`)

---

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall time | 12,182 ms |
| Tool calls | 1 |
| Tokens returned | 0 (no results) |
| Chunks returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

### Answer (Arrow)

`get_context` returned **no results** for this query. The natural-language, cross-cutting question ("How does Arrow handle multiple projects -- indexing, searching, and isolation?") did not match any chunks above the relevance threshold. This is a conceptual/architectural query that spans many files and does not correspond to any single function or keyword cluster.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 25,588 ms | 12,182 ms |
| Tool calls | 9 | 1 |
| Tokens (input) | ~1,920 | 0 |
| Quality | 5/5 | 0/5 |
| Precision | 95% | 0% |
| Completeness | Full architectural picture | No answer |

### Verdict

**Traditional wins decisively.** This is the worst-case scenario for `get_context`: a broad architectural question that spans 6+ files with no single dominant keyword. The relevance-threshold approach correctly avoids returning low-quality noise, but the result is no answer at all. The traditional approach -- targeted Grep for `project_id` patterns, then Read of the key functions -- built a complete picture of the multi-project architecture in under 26 seconds.

**Root cause of Arrow failure:** Cross-cutting architectural queries decompose into many small concepts (project_id filtering, cascade deletes, cwd detection, vector post-filtering, watcher lifecycle) spread across many files. No single chunk scores high enough to pass the relevance cutoff. A `search_code` call with narrower keywords (e.g., "project_id") would likely have returned results, but `get_context` alone could not handle this query shape.

**Recommendation:** For cross-cutting "how does X work" queries, traditional multi-step search remains superior. Arrow's `get_context` is better suited for focused lookups (specific functions, error messages, API signatures). A multi-tool Arrow strategy (e.g., `search_structure` for project-related functions + `search_code` for "project_id") would likely perform better but was not under test.
