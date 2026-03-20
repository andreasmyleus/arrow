# Query 28: "How does the healthcheck work in Docker?"

Category: Needle-in-haystack
Arrow tool(s) under test: get_context

## Round 1 — Traditional

**Timestamps:** start=1774009983222 end=1774009992416
**Wall time:** 9194ms
**Tool calls:** 6 (Glob x2, Read x2, Grep x1, Bash x1)
**Tokens from content:** ~244 (44 lines Dockerfile + 16 lines docker-compose.yml + 1 line Grep results = 61 lines x ~4 tokens)
**Answer quality:** 5
**Precision:** 95%

### Answer

The Docker healthcheck is defined in the Dockerfile at lines 40-41:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/mcp')" || exit 1
```

It works as follows:
- **Interval:** Every 30 seconds, Docker runs the check command.
- **Timeout:** If the check takes longer than 5 seconds, it counts as a failure.
- **Start period:** Docker waits 10 seconds after container start before counting failures, giving the MCP server time to initialize.
- **Command:** Uses Python's `urllib.request` to make an HTTP GET request to `http://localhost:8080/mcp`. If the server is listening and responds, the container is healthy. If it fails or times out, the container is marked unhealthy.

The server runs on port 8080 with HTTP transport (set in the ENTRYPOINT/CMD at lines 43-44).

### Files read
- /Users/andreas/arrow/Dockerfile (44 lines)
- /Users/andreas/arrow/docker-compose.yml (16 lines)

## Round 2 — Arrow (get_context)

**Timestamps:** start=1774009997456 end=1774010003226
**Wall time:** 5770ms
**Tool calls:** 1
**Tokens returned:** 0
**Chunks returned:** 0
**Answer quality:** 1
**Precision:** 0%

### Answer

Arrow returned no results. The Dockerfile is not indexed by Arrow's AST-based chunker, which targets Python source files. The healthcheck directive lives entirely in the Dockerfile, a non-Python config file that falls outside Arrow's indexing scope.

### Files read
- (none)

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 9194ms | 5770ms |
| Tool calls | 6 | 1 |
| Tokens consumed | ~244 | 0 |
| Quality (1-5) | 5 | 1 |
| Precision | 95% | 0% |
| Answered? | Yes | No |

### Notes

This is a clear case where Arrow's index has a blind spot. Arrow indexes Python source code via tree-sitter AST parsing, but the Dockerfile is not a Python file and is therefore not chunked or indexed. The healthcheck is defined entirely in the Dockerfile, so Arrow cannot find it at all. Traditional tools (Glob + Read) handle this trivially by finding and reading the Dockerfile directly. This represents a fundamental limitation of AST-based indexing for non-code configuration files like Dockerfiles, CI configs, and similar infrastructure files.
