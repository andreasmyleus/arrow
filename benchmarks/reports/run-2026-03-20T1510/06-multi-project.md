# Query 06: Multi-Project Handling

**Query:** "How does Arrow handle multiple projects — indexing, searching, and isolation?"
**Category:** get_context — Cross-cutting
**Arrow tool under test:** get_context

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774012292782
**End:** 1774012319431
**Duration:** 26,649 ms

### Tool Calls
| # | Tool | Target |
|---|------|--------|
| 1 | Grep | `project` in storage.py (content, head 60) |
| 2 | Grep | `def.*project` across src/arrow/ |
| 3 | Grep | `project_id\|project_name\|project_path` across src/arrow/ (head 80) |
| 4 | Read | storage.py:507-606 (create_project, get_project, list, update, delete) |
| 5 | Read | indexer.py:70-119 (_resolve_project, index_codebase) |
| 6 | Read | server.py:181-260 (_detect_project_from_cwd, _resolve_project_id) |
| 7 | Read | search.py:395-469 (search method, project filtering) |
| 8 | Read | storage.py:76-105 (projects table schema, files table) |
| 9 | Read | server.py:413-477 (list_projects, project_summary, search_code) |
| 10 | Read | tools_data.py:524-553 (remove_project) |

**Total tool calls:** 10

### Findings

**Schema / Storage isolation:**
- `projects` table with unique name, root_path, remote_url, git info, timestamps.
- `files` table scoped by `project_id` with `UNIQUE(project_id, path)` constraint.
- `chunks` table has `project_id` denormalized for fast search filtering.
- `symbols`, `file_access`, `memories` all carry `project_id` FK with `ON DELETE CASCADE`.
- Dedicated indexes: `idx_files_project`, `idx_chunks_project`.

**Indexing:**
- `_resolve_project()` in indexer.py: looks up project by root_path, creates if new, updates git info.
- `create_project()` uses `ON CONFLICT(name) DO UPDATE` — upsert semantics.
- `index_codebase()` auto-detects git info and associates all files/chunks with the project_id.
- Migration path from v1 (single-project) to v2 (multi-project) schema exists.

**Search isolation:**
- `_detect_project_from_cwd()`: walks up to git root, matches against indexed projects — auto-scopes searches.
- `_resolve_project_id()`: when project is None, auto-detects from cwd to "avoid cross-project contamination."
- BM25 (FTS5) search accepts `project_id` filter.
- Vector search over-fetches 3x when project-scoped, then post-filters chunks by `project_id`.
- Returns `_PROJECT_NOT_FOUND` sentinel (-1) if explicit project name not found, preventing silent fallback.

**Lifecycle:**
- `remove_project()` stops watcher, removes lock, deletes project (cascading to all data).
- `list_projects()` shows stats per project.

### Quality Assessment
- **Quality:** 5/5 — Complete picture of schema, indexing, search isolation, and lifecycle.
- **Precision:** 95% — All findings directly relevant; minor noise from migration code.
- **Estimated tokens consumed:** ~8,500 tokens (grep output + read output)

---

## Round 2 — Arrow (get_context)

**Start:** 1774012322099
**End:** 1774012334343
**Duration:** 12,244 ms

### Tool Calls
| # | Tool | Args |
|---|------|------|
| 1 | get_context | query="How does Arrow handle multiple projects — indexing, searching, and isolation?", project="andreasmyleus/arrow" |

**Total tool calls:** 1

### Result
- **Returned:** 0 chunks, 0 tokens.
- **Message:** "No results" with suggestions to try broader keywords or use search_structure().

### Quality Assessment
- **Quality:** 1/5 — No results returned at all.
- **Precision:** N/A — Nothing to evaluate.
- **Tokens consumed:** ~50 tokens (error message only)

---

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration | 26,649 ms | 12,244 ms |
| Tool calls | 10 | 1 |
| Tokens consumed | ~8,500 | ~50 |
| Quality (1-5) | 5 | 1 |
| Precision | 95% | N/A |
| Completeness | Full picture across 4 files | No results |

### Analysis

**Arrow failed this query entirely.** The natural-language question "How does Arrow handle multiple projects — indexing, searching, and isolation?" returned zero results despite the codebase having 835 indexed chunks with extensive multi-project logic spread across storage.py, indexer.py, server.py, and search.py.

This is a cross-cutting architectural query — it spans multiple files and concepts (schema design, indexing flow, search filtering, cwd detection). The relevance-threshold approach in get_context likely found no single chunk that scored highly enough against this broad, conceptual query. The term "multiple projects" may not appear verbatim in any chunk, and the query's breadth dilutes matching against any specific function.

**Traditional approach excelled** because Grep naturally finds the `project` concept across the codebase, and targeted reads of key functions (create_project, _resolve_project, _detect_project_from_cwd, search with project_id filtering) build a complete understanding.

**Verdict:** Arrow's relevance-gated retrieval struggles with broad architectural questions that require synthesizing concepts spread across many files. The traditional multi-step Grep+Read approach is clearly superior for cross-cutting "how does X work" queries. This is a known weakness pattern for single-shot retrieval on architectural questions.
