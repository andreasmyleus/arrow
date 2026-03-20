# Query 1: "Review the Docker setup — how is it configured, what does it build, and how would I run it?"

Category: get_context — Primary retrieval
Arrow tool(s) under test: get_context

## Round 1 — Traditional
**Timestamps:** start=1774007779247 end=1774007794646
**Wall time:** 15399ms
**Tool calls:** 9 (Glob x3, Grep x2, Read x3, Bash x0)
**Tokens from content:** ~364 (91 lines across 3 files + grep output)
**Answer quality:** 5/5
**Precision:** 95%

### Answer
The Docker setup is a multi-stage build using `python:3.12-slim`:

**Dockerfile (multi-stage):**
- **Builder stage:** Installs build-essential and git, copies `pyproject.toml`, `README.md`, `LICENSE`, and `src/`, runs `pip install`, then pre-downloads the Jina embedding model at build time so it's cached in the layer.
- **Runtime stage:** Uses a clean `python:3.12-slim` image, installs only `libgomp1` (for ONNX/usearch), copies installed packages, the `arrow` binary, source, and cached model from the builder stage.
- Exposes port 8080, sets up a healthcheck against `http://localhost:8080/mcp`, and runs `python -m arrow --transport http --port 8080` as the entrypoint.
- Two volumes: `/data` (for SQLite DB and vector index) and `/workspace` (for mounting the codebase to index).
- Environment variables `ARROW_DB_PATH` and `ARROW_VECTOR_PATH` point into `/data`.

**docker-compose.yml:**
- Single service `arrow`, builds from `.`, maps port 8080, mounts a named volume `arrow-data` to `/data` and `$WORKSPACE_PATH` (defaults to `.`) read-only to `/workspace`.
- Restart policy: `unless-stopped`.

**How to run:**
- `docker build -t arrow . && docker run -v /path/to/project:/workspace:ro -p 8080:8080 arrow`
- Or with compose: `WORKSPACE_PATH=/path/to/project docker compose up -d`
- Then register: `claude mcp add --transport http arrow http://localhost:8080/mcp`
- Multi-arch: `docker buildx build --platform linux/amd64,linux/arm64 -t arrow:latest .`

**.dockerignore:** Excludes `.venv/`, `.git/`, `__pycache__/`, `*.db`, `*.usearch`, `.arrow/`, etc.

### Files read
- /Users/andreas/arrow/Dockerfile (44 lines)
- /Users/andreas/arrow/docker-compose.yml (16 lines)
- /Users/andreas/arrow/.dockerignore (15 lines)
- /Users/andreas/arrow/README.md (grep output, ~16 relevant lines)

## Round 2 — Arrow
**Timestamps:** start=1774007797675 end=1774007807395
**Wall time:** 9720ms
**Tool calls:** 1 (get_context x1)
**Tokens from content:** 0 (no results returned)
**Chunks returned:** 0
**Answer quality:** 0/5
**Precision:** N/A

### Answer
Arrow returned **no results** for this query. The response was: "No results for: Review the Docker setup..." with suggestions to try broader keywords or use other tools.

This is expected behavior: Arrow indexes code via tree-sitter AST chunking (functions, classes, methods). The Dockerfile, docker-compose.yml, and .dockerignore are not code files parsed by tree-sitter, so they are not indexed and cannot be found by `get_context`.

### Observations
- **Traditional wins decisively.** Arrow returned nothing; traditional tools provided a complete, thorough answer.
- **Root cause:** Arrow's indexer focuses on source code (Python, JS, etc.) parsed by tree-sitter. Configuration files like Dockerfile, docker-compose.yml, and .dockerignore are not indexed as semantic chunks, so they are invisible to `get_context`.
- **This is a known limitation category:** Queries about infrastructure/config files (Docker, CI/CD, Terraform, Makefiles) will consistently fail with Arrow unless these file types are added to the chunking pipeline.
- Arrow did return the response quickly (~9.7s including tool fetch overhead), but speed is irrelevant when the answer is empty.
- The CLAUDE.md mentions Arrow now has "section-aware chunkers for non-code files (TOML, YAML, JSON, Markdown, Dockerfile)" per a recent commit, but these chunks were apparently not indexed or not matched for this query.
