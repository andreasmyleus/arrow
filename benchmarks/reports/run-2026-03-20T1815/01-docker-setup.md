# Query 1: "Review the Docker setup — how is it configured, what does it build, and how would I run it?"

Category: Targeted lookup
Arrow tool(s) under test: get_context

## Round 1 — Traditional

**Timestamps:** start=1774009842319 end=1774009849191
**Wall time:** 6872ms
**Tool calls:** 7 (Glob x3, Read x3, Bash x1)
**Tokens from content:** ~304 (45 lines Dockerfile + 16 lines docker-compose.yml + 15 lines .dockerignore = 76 lines x ~4 tokens)
**Answer quality:** 5
**Precision:** 100%

### Answer

The Docker setup consists of three files:

**Dockerfile** — A multi-stage build based on `python:3.12-slim`:
- **Builder stage:** Installs build-essential and git, copies `pyproject.toml`, `README.md`, `LICENSE`, and `src/`, runs `pip install .`, then pre-downloads the Jina embedding model into `/root/.arrow/models`.
- **Runtime stage:** Starts from a fresh `python:3.12-slim`, installs only `libgomp1` (for ONNX/usearch), copies installed packages, the `arrow` CLI binary, source, and the cached model from the builder. Sets env vars `ARROW_DB_PATH=/data/index.db` and `ARROW_VECTOR_PATH=/data/vectors.usearch`. Declares volumes `/data` (persistent index) and `/workspace` (codebase to index). Exposes port 8080, adds a healthcheck hitting `/mcp`, and runs `python -m arrow --transport http --port 8080`.

**docker-compose.yml** — Single service `arrow` that builds from `.`, maps port 8080, mounts a named volume `arrow-data` to `/data` and the host `$WORKSPACE_PATH` (defaulting to `.`) read-only to `/workspace`. Restarts unless stopped.

**.dockerignore** — Excludes `.venv/`, `.git/`, `__pycache__/`, database files (`*.db`, `*.sqlite`, `*.usearch`), build artifacts, and `.arrow/`.

**To run:** `WORKSPACE_PATH=/path/to/your/code docker compose up --build` or simply `docker compose up` to index the current directory.

### Files read
- /Users/andreas/arrow/Dockerfile (44 lines)
- /Users/andreas/arrow/docker-compose.yml (16 lines)
- /Users/andreas/arrow/.dockerignore (15 lines)

## Round 2 — Arrow

**Timestamps:** start=1774009853609 end=1774009862411
**Wall time:** 8802ms
**Tool calls:** 1 (get_context x1)
**Tokens from content:** 0 (Arrow-reported)
**Chunks returned:** 0
**Answer quality:** 0
**Precision:** 0%

### Answer

Arrow returned no results. It could not answer the question.

### Observations

**Traditional wins decisively.** Arrow's index is built from tree-sitter AST parsing, which only processes source code files (Python, JS, etc.). Configuration files like `Dockerfile`, `docker-compose.yml`, and `.dockerignore` are not indexed at all. This means any query about Docker setup, CI/CD configuration, or other non-source-code files will return zero results from Arrow.

Traditional tools (Glob + Read) are perfectly suited for this kind of targeted lookup — a few quick glob patterns locate the three Docker-related files, and reading them gives a complete picture in ~76 lines of content.

This is a category of query where Arrow has a structural blind spot: infrastructure and configuration files outside the supported language set. The traditional approach was also faster in wall time (6.9s vs 8.8s) while delivering a complete answer.
