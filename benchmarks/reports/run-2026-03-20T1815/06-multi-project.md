# Query 6: "How does Arrow handle multiple projects — indexing, searching, and isolation?"

Category: Architecture understanding
Arrow tool(s) under test: get_context

## Round 1 — Traditional

**Timestamps:** start=1774009863793 end=1774009887760
**Wall time:** 23967ms
**Tool calls:** 9 (Grep x6, Read x3)
**Tokens from content:** ~1200 (approx 300 lines read across storage.py, server.py, search.py, indexer.py at ~4 tokens/line)
**Answer quality:** 5
**Precision:** 95%

### Answer

Arrow's multi-project support spans four layers: storage schema, indexing, search, and runtime isolation.

**Storage (storage.py):** A `projects` table holds per-project metadata (name, root_path, remote_url, git info, is_remote flag). Every `files` row has a `project_id` FK with `UNIQUE(project_id, path)` so the same relative path can exist in different projects without collision. `chunks` has a denormalized `project_id` for fast search filtering. `ON DELETE CASCADE` ensures deleting a project removes all its files, chunks, FTS entries, and memories. There is also a v1-to-v2 migration (`_migrate_v1_to_v2`) that retrofits multi-project support onto older single-project databases.

**Indexing (indexer.py):** `_resolve_project()` looks up or creates a project by root path via `get_project_by_root()`. New projects are auto-detected from git info (name, branch, commit, remote URL). `index_codebase()` scopes all file operations (add, update, delete) to a single `project_id`. Remote content indexing (`index_remote_content`, `index_git_commit`) creates separate project entries with `is_remote=True` or snapshot names like `"org/repo@ref"`. PR indexing creates two projects (base and head) with names like `"org/repo@PR#N-base"`.

**Search (search.py):** The `search()` method accepts an optional `project_id`. BM25/FTS5 search joins `chunks_fts` with `chunks` to filter by `project_id`. Vector search over-fetches by 3x when project-scoped, then post-filters results by `project_id` since the usearch vector index is global (not partitioned per project). `count_fts_hits` and `search_regex` similarly accept `project_id` for scoping.

**Runtime isolation (server.py):** `_resolve_project_id()` auto-detects the current project from cwd by walking up to the git root and matching against indexed project root paths. This prevents "cross-project contamination" (e.g., returning pydantic results while working in arrow). Each project gets its own threading lock (`_project_locks`) for write serialization during concurrent indexing. Each local project gets its own file watcher (`_watchers` dict keyed by project_id). If a project name is explicitly provided but not found, `_PROJECT_NOT_FOUND` sentinel (-1) is returned so callers don't silently fall back to all-projects search.

### Files read
- /Users/andreas/arrow/src/arrow/storage.py (schema, CRUD, FTS, regex search)
- /Users/andreas/arrow/src/arrow/server.py (project resolution, locks, watchers)
- /Users/andreas/arrow/src/arrow/search.py (hybrid search project scoping)
- /Users/andreas/arrow/src/arrow/indexer.py (project creation, indexing scoping)

## Round 2 — Arrow

**Timestamps:** start=1774009890208 end=1774009902600
**Wall time:** 12392ms
**Tool calls:** 1 (get_context x1)
**Tokens from content:** 0 (Arrow-reported)
**Chunks returned:** 0
**Answer quality:** 0
**Precision:** 0%

### Answer

Arrow returned no results. The query "How does Arrow handle multiple projects — indexing, searching, and isolation?" produced zero chunks, despite the codebase containing extensive multi-project logic across all major modules.

### Observations

**Traditional wins decisively.** The natural-language architecture question returned zero results from Arrow's `get_context`. This is a retrieval failure — the relevant code absolutely exists in the index (1106 chunks across 97 files), but the query phrasing did not match well enough against the BM25 or vector search to pass the relevance threshold.

The query is conceptual and cross-cutting: "multi-project handling" is a design pattern spread across four files, not a single function or class. Terms like "isolation," "multiple projects," and "indexing" are generic and may not rank highly against the specific code tokens in storage schemas, lock dictionaries, and project resolution functions. Arrow's relevance-first approach (only returning chunks above a threshold) means it prefers returning nothing over returning low-confidence results — which is the right default for most queries but fails on broad architectural questions.

Traditional tools required 9 calls and ~24 seconds but produced a comprehensive, accurate answer covering all four layers of multi-project support. The Grep-first strategy (searching for "project" across key files) efficiently located all relevant code paths, and targeted Read calls filled in the details.

This query type — "how does X architectural concern work across the codebase" — is a weakness for semantic search tools that return individual chunks. The answer requires synthesizing small pieces from many locations, which manual exploration handles well.
