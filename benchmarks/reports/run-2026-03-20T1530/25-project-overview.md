# Query 25: "Give me a high-level overview of this project — languages, structure, entry points"

Category: project_summary — Project overview
Arrow tool(s) under test: project_summary

## Round 1 — Traditional
**Timestamps:** start=1774007895542 end=1774007913854
**Wall time:** 18312ms
**Tool calls:** 10 (Bash x2, Glob x4, Read x4)
**Tokens from content:** ~650 (pyproject.toml 50 lines, cli.py 30 lines, server.py 40 lines, __main__.py 5 lines, Dockerfile 15 lines, directory listings, glob results)
**Answer quality:** 5/5
**Precision:** 95%

### Answer
**Arrow** (arrow-mcp v0.5.0) is a local MCP server that gives Claude Code intelligent code indexing and retrieval. Python 3.10+, MIT license.

**Languages:** Predominantly Python. Config files in TOML, YAML, Dockerfile, JSON. Documentation in Markdown.

**Structure:**
- `src/arrow/` — 16 Python source modules (server, indexer, search, chunker, embedder, storage, vector_store, cli, config, watcher, git_utils, discovery, hasher, tools_analysis, tools_github, tools_data)
- `tests/` — 27 test files covering core, server, search, memory, impact analysis, symbol resolution, etc.
- `benchmarks/` — 2 benchmark scripts plus reports
- Root — pyproject.toml, Dockerfile, docker-compose.yml, arrow.toml, README.md, LICENSE

**Entry points:**
- CLI: `arrow = "arrow.cli:main"` (defined in pyproject.toml `[project.scripts]`)
- Module: `python -m arrow` via `__main__.py` which calls `cli.main()`
- MCP server: `server.py` creates a `FastMCP("arrow")` instance
- Docker: entrypoint runs `python -m arrow --transport http --port 8080`

**Key dependencies:** mcp, tree-sitter, tree-sitter-languages, usearch, onnxruntime, tiktoken, watchdog, xxhash, huggingface-hub, numpy.

### Files read
- /Users/andreas/arrow/pyproject.toml (50 lines)
- /Users/andreas/arrow/src/arrow/cli.py (30 lines)
- /Users/andreas/arrow/src/arrow/server.py (40 lines)
- /Users/andreas/arrow/src/arrow/__main__.py (5 lines)
- /Users/andreas/arrow/Dockerfile (15 lines)
- Glob results for src/, tests/, benchmarks/

## Round 2 — Arrow
**Timestamps:** start=1774007913854 end=1774007921800
**Wall time:** 7946ms
**Tool calls:** 1 (project_summary x1)
**Tokens from content:** ~180 (structured JSON summary)
**Chunks returned:** 0 (summary tool, not chunk-based)
**Answer quality:** 4/5
**Precision:** 90%

### Answer
Arrow returned a structured JSON summary covering:

**Languages:** Python (49 files), Markdown (20), YAML (2), TOML (2), JSON (1), gitignore (1), dockerignore (1), Dockerfile (1). Total: 78 files, 954 chunks, 953 symbols.

**Structure:**
- `tests/` — 27 files
- `benchmarks/` — 20 files
- `src/` — 18 files
- `.` (root) — 12 files
- `.github/` — 1 file

**Entry points:** `pyproject.toml`, `src/arrow/server.py`

**Missing vs Traditional:**
- No dependency list (would need pyproject.toml read)
- Entry points only list 2 (misses `__main__.py` and the CLI script definition)
- No description of what the project does or its purpose
- No mention of Docker entrypoint

### Observations
- **Traditional provides a richer answer** with project purpose, dependencies, all entry points (CLI, module, MCP server, Docker), and deeper structural understanding.
- **Arrow is 2.3x faster** (7.9s vs 18.3s) and requires only 1 tool call vs 10, delivering an excellent structured overview with language distribution and file counts.
- **Arrow's entry point detection** correctly identifies pyproject.toml and server.py but misses the CLI script entry and `__main__.py`.
- **Arrow excels at quantitative overview** — exact file counts per language and directory, total chunks/symbols indexed — data that would require many tool calls to derive traditionally.
- **Traditional excels at qualitative overview** — what the project does, key dependencies, how to run it, architectural narrative.
- **Complementary strengths:** The ideal project overview would combine Arrow's structured stats with a few targeted file reads for context. Arrow provides an excellent starting point that covers 80% of the overview in 1 call.
