# Query 25: Project Overview

**Query:** "Give me a high-level overview of this project — languages, structure, entry points"
**Category:** project_summary — Project overview
**Arrow tool under test:** `project_summary`

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 16,239 ms |
| Tool calls | 9 (ls, Glob x3, Read x3, Bash x2) |
| Tokens (est.) | ~4,500 input |
| Quality | 5/5 |
| Precision | 95% |

### Approach
1. Listed top-level directory to understand project layout.
2. Globbed `**/*.py` in `src/`, `tests/`, and `benchmarks/` to enumerate all Python files.
3. Read `pyproject.toml` for project metadata, dependencies, and entry points.
4. Read `server.py`, `cli.py`, and `__main__.py` headers to identify entry points and architecture.
5. Ran `wc -l` to get line counts per module and total (8,905 lines across 18 source files).

### Findings
- **Language:** 100% Python (3.10+), with TOML/YAML/Dockerfile support files.
- **Structure:** `src/arrow/` (18 modules, 8,905 lines), `tests/` (27 test files), `benchmarks/` (2 files).
- **Entry points:** CLI via `arrow.cli:main` (pyproject.toml script), MCP server via `server.py` FastMCP instance, `__main__.py` for `python -m arrow`.
- **Key modules by size:** storage.py (1,471), server.py (1,178), chunker.py (1,143), indexer.py (867), cli.py (859), search.py (785).
- **Dependencies:** mcp, tree-sitter, xxhash, tiktoken, usearch, onnxruntime, watchdog, numpy, etc.

---

## Round 2 — Arrow (`project_summary`)

| Metric | Value |
|--------|-------|
| Wall time | 10,986 ms |
| Tool calls | 1 |
| Tokens (est.) | ~350 input |
| Quality | 4/5 |
| Precision | 85% |

### Output Summary
Single JSON response with:
- **Total files:** 63, **chunks:** 835, **symbols:** 834
- **Languages:** python (49), markdown (5), yaml (2), toml (2), json (1), dockerfile (1), gitignore (1), dockerignore (1)
- **Structure:** tests (27), src (18), root (12), benchmarks (5), .github (1)
- **Entry points:** `pyproject.toml`, `src/arrow/server.py`
- **Index duration:** 0.04s (incremental)

### What was missing vs Traditional
- No line counts or module-level size breakdown.
- No dependency list.
- Entry points limited to 2 (missed `__main__.py` and the CLI script endpoint `arrow.cli:main`).
- No architectural narrative (which module does what).

---

## Comparison

| Dimension | Traditional | Arrow | Winner |
|-----------|------------|-------|--------|
| Wall time | 16,239 ms | 10,986 ms | Arrow |
| Tool calls | 9 | 1 | Arrow |
| Tokens consumed | ~4,500 | ~350 | Arrow (13x less) |
| Quality (1-5) | 5 | 4 | Traditional |
| Precision | 95% | 85% | Traditional |
| Completeness | Full (deps, sizes, architecture) | Good (languages, structure, entry points) | Traditional |
| Effort | High (multi-step exploration) | Minimal (single call) | Arrow |

## Verdict

**Arrow wins on efficiency** — 1 tool call, ~350 tokens, ~11 seconds vs 9 calls, ~4,500 tokens, ~16 seconds. The `project_summary` tool delivers a well-structured JSON covering languages, directory structure, and entry points in a single call.

**Traditional wins on depth** — provides module-level line counts, dependency lists, architectural details, and identifies all entry points (including `__main__.py` and the pyproject.toml script endpoint). For a "high-level overview" question, Arrow's output is sufficient but slightly incomplete on entry points and lacks the per-module size breakdown that helps prioritize where to look.

**Overall:** Arrow is the right first call for this query type, but a follow-up with `file_summary` on key modules would be needed to match the traditional depth. For a quick orientation, Arrow is clearly more efficient.
