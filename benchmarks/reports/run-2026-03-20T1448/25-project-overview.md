# Query 25 — Project Overview

**Query:** "Give me a high-level overview of this project — languages, structure, entry points"
**Category:** Project overview
**Arrow tool(s) under test:** `project_summary`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 23,729 ms |
| Tool calls | 11 |
| Lines read | ~285 |
| Tokens (est.) | ~1,140 |
| Quality | 5/5 |
| Precision | 95% |

### Answer (Traditional)

- **Language:** 100% Python (8,880 lines in `src/`, 4,713 in `tests/`)
- **Structure:**
  - `src/arrow/` — 17 source modules (server, indexer, search, storage, chunker, embedder, vector_store, git_utils, discovery, hasher, watcher, config, cli, tools_analysis, tools_github, tools_data)
  - `tests/` — 28 test files covering core, search, analysis, memory, import/export, etc.
  - `benchmarks/` — bench scripts and reports
  - Root — `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `arrow.toml`
- **Entry points:**
  - CLI: `arrow` command via `arrow.cli:main` (pyproject.toml `[project.scripts]`)
  - Module: `python -m arrow` via `__main__.py`
  - MCP server: `server.py` creates `FastMCP("arrow")` instance
  - Docker: `ENTRYPOINT ["python", "-m", "arrow"]` with HTTP transport on port 8080
- **Build:** Hatchling, Python 3.10+, key deps: mcp, tree-sitter, usearch, onnxruntime, watchdog

### Method

Listed top-level directory, globbed for `*.py` and other language files, read `pyproject.toml`, `cli.py`, `__main__.py`, `server.py`, and `Dockerfile`. Counted lines in src and tests. No other languages found.

---

## Round 2 — Arrow (`project_summary`)

| Metric | Value |
|--------|-------|
| Wall time | 13,070 ms |
| Tool calls | 1 |
| Chunks returned | 0 (structured JSON) |
| Tokens (est.) | ~250 |
| Quality | 4/5 |
| Precision | 85% |

### Answer (Arrow)

- **Languages:** markdown (82 files), python (49), yaml (2), toml (2), json (1), gitignore (1), dockerignore (1), dockerfile (1) — 140 total files
- **Structure:** benchmarks (82 files), tests (27), src (18), root (12), .github (1)
- **Entry points:** `pyproject.toml`, `src/arrow/server.py`
- **Stats:** 1,440 chunks, 1,439 symbols, indexed in 0.05s

### What was missing from Arrow

- No line-of-code counts or language percentages by code volume (markdown dominates by file count due to benchmark reports, which is misleading for a pure-Python project)
- Only 2 entry points identified; missed `__main__.py` (module entry), CLI script definition in pyproject.toml, and Docker entrypoint
- No dependency information or build system details
- No description of what each module does or how they relate

---

## Comparison

| Dimension | Traditional | Arrow | Winner |
|-----------|------------|-------|--------|
| Wall time | 23.7s | 13.1s | Arrow |
| Tool calls | 11 | 1 | Arrow |
| Tokens used | ~1,140 | ~250 | Arrow |
| Completeness | Full: LOC, deps, all entry points, build system | Partial: file counts, basic structure, 2 entry points | Traditional |
| Language accuracy | Correctly identifies as pure Python project | Misleading: markdown appears dominant (82/140 files are benchmark reports) | Traditional |
| Entry points | 4 identified (CLI, module, MCP, Docker) | 2 identified (pyproject.toml, server.py) | Traditional |
| Actionability | High — enough to start contributing | Medium — good bird's-eye view but needs follow-up | Traditional |

## Verdict

**Arrow wins on efficiency** (1 tool call, 78% less tokens, 45% faster), but **Traditional wins on quality** for this particular query. The `project_summary` tool provides a useful quick snapshot, but has two notable issues: (1) it counts files rather than lines of code, which makes markdown-heavy repos look like documentation projects rather than code projects, and (2) entry point detection is limited — it found the two most important ones but missed alternative entry points. For a "high-level overview" query, the traditional approach delivers a more complete and accurate picture because it can read configuration files and understand the project holistically. Arrow's output is best suited as a starting point to be supplemented with targeted reads.

**Quality: Traditional 5/5, Arrow 4/5**
**Efficiency: Arrow clearly superior**
**Overall: Traditional wins on answer quality; Arrow wins on speed**
