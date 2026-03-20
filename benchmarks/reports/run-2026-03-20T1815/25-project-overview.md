# Query 25: Project Overview

**Category:** Project overview
**Query:** "Give me a high-level overview of this project — languages, structure, entry points"
**Arrow tool:** `project_summary`

## Round 1 — Traditional Tools

| Metric | Value |
|--------|-------|
| Duration | 20,689 ms |
| Tool calls | 11 (4 Bash, 3 Glob, 4 Read) |
| Estimated tokens | ~1,200 |
| Quality | 4/5 |
| Precision | 80% |

**Approach:** Listed top-level directory and `src/arrow/`, read `pyproject.toml` for metadata/dependencies, globbed for all `.py` files in src and tests, read `cli.py`, `__main__.py`, `server.py`, and `Dockerfile` headers to identify entry points and architecture.

**Findings:** Python 3.10+ MCP server project. 18 source files in `src/arrow/`, 27 test files. Entry points: `arrow` CLI command (`cli.py:main`), `python -m arrow`, MCP server via FastMCP. Docker multi-stage build. Dependencies include tree-sitter, ONNX, usearch, watchdog.

**Limitations:** Could not get language distribution or file counts per directory without additional commands. Missing the benchmarks directory (55 files) entirely — never explored it. No automatic detection of non-Python files (markdown, yaml, etc.).

## Round 2 — Arrow (`project_summary`)

| Metric | Value |
|--------|-------|
| Duration | 8,828 ms |
| Tool calls | 1 |
| Tokens returned | ~350 |
| Quality | 5/5 |
| Precision | 95% |

**Result:** Single call returned structured JSON with:
- **Languages:** markdown (55), python (49), yaml (2), toml (2), json (1), gitignore (1), dockerignore (1), dockerfile (1) — 113 total files
- **Structure:** benchmarks (55), tests (27), src (18), root (12), .github (1)
- **Entry points:** `pyproject.toml`, `src/arrow/server.py`
- **Stats:** 1,225 chunks, 1,224 symbols indexed

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Duration | 20,689 ms | 8,828 ms | Arrow (2.3x faster) |
| Tool calls | 11 | 1 | Arrow (11x fewer) |
| Tokens | ~1,200 | ~350 | Arrow (3.4x fewer) |
| Quality | 4/5 | 5/5 | Arrow |
| Precision | 80% | 95% | Arrow |

**Analysis:** The traditional approach required extensive exploration — listing directories, reading config files, globbing for files — and still missed the benchmarks directory entirely (55 files / half the repo). Arrow's `project_summary` returned a complete, structured overview in a single call: language distribution across all file types, directory-level file counts, and identified entry points. The traditional approach gave deeper insight into dependencies (from reading pyproject.toml) but the core question about languages, structure, and entry points was answered more completely by Arrow. This is exactly the kind of "orientation" query where a pre-built index shines.
