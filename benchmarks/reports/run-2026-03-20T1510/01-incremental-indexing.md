# Query 1: "How does the indexer decide which files to re-index vs skip on incremental updates?"

Category: get_context — Primary retrieval
Arrow tool(s) under test: get_context

## Round 1 — Traditional

**Timestamps:** start=1774012273441 end=1774012290768
**Wall time:** 17327ms
**Tool calls:** 5 (Grep×3, Read×2)
**Tokens from content:** ~780
**Answer quality:** 5
**Precision:** 95%

### Answer

The indexer uses xxHash3-128 content hashing to decide which files to re-index vs skip. The flow in `index_codebase()` (indexer.py:102-236) works as follows:

1. **File discovery**: `discover_files(root)` enumerates all eligible files in the codebase.
2. **Hash current file**: For each discovered file, `hash_file()` (hasher.py:15-24) computes an xxHash3-128 digest by reading the file in 64KB chunks.
3. **Compare against stored hash**: Unless `force=True`, it looks up the file in the database via `storage.get_file(rel_path, project_id)`. If the stored `content_hash` matches the freshly computed hash, the file is skipped (`files_skipped += 1`).
4. **Re-index if changed**: If the hash differs (or no prior record exists), the file is read, re-chunked via tree-sitter AST parsing, old chunks are deleted, new chunks are inserted, and embeddings are queued for background generation.
5. **Deleted file cleanup**: After scanning, any files in the index whose paths were not seen on disk are removed from the database.
6. **Force mode**: The `force=True` flag bypasses the hash comparison entirely, re-indexing all files unconditionally.

The same hash-comparison pattern is also used in `index_remote_files()` and `index_git_commit()` for remote/content-based indexing (using `hash_content()` instead of `hash_file()`).

### Files read
- src/arrow/indexer.py (100 lines at offset 100, 50 lines at offset 199)
- src/arrow/hasher.py (25 lines)

## Round 2 — Arrow

**Timestamps:** start=1774012293468 end=1774012310705
**Wall time:** 17237ms (but required 3 get_context calls; first 2 returned no results)
**Tool calls:** 3 (get_context×3, only 1 successful)
**Tokens from content:** 2369 (Arrow-reported)
**Chunks returned:** 8
**Answer quality:** 5
**Precision:** 85%

### Answer

The answer derived from Arrow's successful response is the same as Round 1. The `index_codebase()` method in `indexer.py` computes an xxHash3-128 hash for each file on disk using `hash_file()`, then compares it against the stored `content_hash` in the database. If they match and `force` is not set, the file is skipped. Otherwise, the file is fully re-indexed: old chunks deleted, new chunks created, embeddings queued. Deleted files (present in index but absent on disk) are cleaned up at the end.

Arrow additionally surfaced useful context not found in Round 1: the `detect_stale_index()` tool (tools_data.py:23-87) which uses the same hash comparison externally to report index drift, the CLI `cmd_index` function, the `server.py` wrapper with project locking, and a test for force re-indexing.

### Observations

- **Query sensitivity**: The first two natural-language queries to `get_context` returned zero results. Only the third attempt using function/variable names as keywords ("index_codebase hash_file content_hash force") succeeded. This is a significant usability issue — the tool should handle conceptual queries about incremental indexing.
- **When it worked, Arrow was comprehensive**: The successful call returned 8 highly relevant chunks spanning indexer.py, hasher.py, server.py, tools_data.py, cli.py, and tests — broader coverage than the traditional approach in a single call.
- **Token efficiency**: Arrow returned 2369 tokens (more than the ~780 from traditional), but it included extra context (detect_stale_index, CLI, tests, server wrapper) that was genuinely useful. The traditional approach was more surgical.
- **Wall time**: Comparable once adjusted — the successful Arrow call alone was fast, but the failed queries added overhead. Traditional was 1 round of parallel searches.
- **Winner**: Traditional wins on reliability (worked first try) and precision. Arrow wins on breadth of context when it works. The natural language query failure is the key issue to address.
