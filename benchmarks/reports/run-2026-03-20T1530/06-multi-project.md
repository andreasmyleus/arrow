# Benchmark 06 — Multi-Project Handling

**Query:** "How does Arrow handle multiple projects — indexing, searching, and isolation?"

## Round 1 — Traditional Tools (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Start | 1774007800084 |
| End | 1774007831005 |
| Duration | 30,921 ms |
| Tool calls | 10 (1 Glob, 3 Grep, 6 Read) |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Arrow handles multiple projects through a comprehensive multi-project architecture:

**Indexing:**
- `ProjectRecord` dataclass stores per-project metadata (name, root_path, remote_url, git info, timestamps) in a `projects` table with unique name constraint.
- `Indexer._resolve_project()` finds or creates a project by root path, auto-detecting git org/repo name via `get_git_info()`.
- `storage.create_project()` uses `INSERT ... ON CONFLICT(name) DO UPDATE` for upsert semantics.
- All files and chunks carry a `project_id` foreign key with `ON DELETE CASCADE`.
- The `files` table has a `UNIQUE(project_id, path)` constraint ensuring path uniqueness per project.

**Searching:**
- `_resolve_project_id()` in `server.py` auto-detects the current project from cwd to avoid cross-project contamination. Falls back to all-projects search only if cwd doesn't match any indexed project.
- BM25/FTS search accepts `project_id` and joins against chunks to filter: `WHERE cf.chunks_fts MATCH ? AND c.project_id = ?`.
- Vector search post-filters results by `project_id` after retrieval (over-fetches 3x when project-scoped).
- Search results include `project_name` field so callers see which project each result came from.

**Isolation:**
- `remove_project()` stops the watcher, removes locks, and cascading-deletes all project data.
- Stats, test files, file access, symbols, and memories are all scoped by `project_id`.
- `_check_project_id()` returns an error with available projects list when a specified project is not found, preventing silent fallback.

## Round 2 — Arrow MCP (`get_context`)

| Metric | Value |
|---|---|
| Start | 1774007834184 |
| End | 1774007840791 |
| Duration | 6,607 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

### Findings

The `get_context` call returned **no results** for this query. The natural-language phrasing "How does Arrow handle multiple projects" did not match any chunks above the relevance threshold. This is a conceptual/architectural question that spans many files and functions — the kind of query where keyword-based and vector search struggle because no single chunk contains the full answer.

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Duration | 30.9s | 6.6s |
| Tool calls | 10 | 1 |
| Quality | 5/5 | 0/5 |
| Precision | 95% | 0% |
| Completeness | Full architectural understanding across 6 files | No results returned |

### Analysis

This query represents a **worst case for Arrow**: a broad architectural question that requires synthesizing information scattered across `storage.py`, `server.py`, `search.py`, `indexer.py`, and `tools_data.py`. No single chunk contains a holistic answer about "multi-project handling," so relevance-based retrieval correctly determines that no individual chunk is highly relevant — but the aggregate of many moderately relevant chunks would have answered the question.

The traditional approach excelled here because it could iteratively narrow down from broad `Grep` searches to targeted `Read` calls, building up a cross-file understanding. This is the type of query where manual exploration significantly outperforms single-shot retrieval.

Arrow's speed advantage (5x faster) is meaningless when zero useful content is returned.
