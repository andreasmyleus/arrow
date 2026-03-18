"""Comprehensive Arrow vs Traditional benchmark — 100+ queries of varying complexity.

Measures token usage and latency for Arrow's get_context vs the traditional
approach of reading entire files with Glob + Grep + Read.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arrow.indexer import Indexer
from arrow.search import HybridSearcher
from arrow.storage import Storage

# ---------------------------------------------------------------------------
# Query catalog — 100+ queries across 10 complexity tiers
# ---------------------------------------------------------------------------

QUERIES = {
    # ── Tier 1: Single symbol lookup (simplest) ──────────────────────────
    "Symbol lookup": [
        "hash_content function",
        "hash_file function",
        "count_tokens function",
        "decompress_content function",
        "compress_content function",
        "detect_language function",
        "SearchResult class",
        "FileRecord dataclass",
        "ChunkRecord dataclass",
        "SymbolRecord dataclass",
        "ImportRecord dataclass",
        "Storage class",
        "VectorStore class",
        "HybridSearcher class",
        "Indexer class",
    ],

    # ── Tier 2: Specific method lookup ───────────────────────────────────
    "Method lookup": [
        "upsert_file method",
        "insert_chunks_batch",
        "search_fts method",
        "get_file_by_id",
        "get_chunks_by_ids",
        "search_symbols",
        "embed_batch method",
        "embed_query method",
        "index_codebase method",
        "get_context method",
        "reciprocal_rank_fusion",
        "generate_project_summary",
        "_extract_structure",
        "_extract_imports",
        "_embed_chunks_async",
    ],

    # ── Tier 3: Keyword search (single concept) ─────────────────────────
    "Single concept": [
        "FTS5 full text search",
        "BM25 scoring",
        "vector search",
        "cosine similarity",
        "token budget",
        "zstd compression",
        "xxhash hashing",
        "tree-sitter parser",
        "watchdog file watcher",
        "SQLite WAL mode",
    ],

    # ── Tier 4: Two-concept intersection ─────────────────────────────────
    "Two concepts": [
        "hybrid search ranking",
        "vector store persistence",
        "incremental indexing hash",
        "FTS5 trigger sync",
        "chunk token counting",
        "file discovery gitignore",
        "symbol extraction AST",
        "import dependency tracking",
        "embedding ONNX runtime",
        "MCP tool registration",
    ],

    # ── Tier 5: How-does-X-work questions ────────────────────────────────
    "How it works": [
        "how does hybrid search combine BM25 and vector results",
        "how does incremental indexing detect changed files",
        "how does the token budget trimming work in get_context",
        "how does the FTS5 virtual table sync with chunk inserts",
        "how does the chunker handle files without tree-sitter support",
        "how does the embedder download and cache the ONNX model",
        "how does the file watcher debounce rapid changes",
        "how does the CLI dispatch subcommands",
        "how does the MCP server initialize global state",
        "how are imports extracted from Python files",
    ],

    # ── Tier 6: Cross-file tracing ───────────────────────────────────────
    "Cross-file": [
        "data flow from file discovery to storage",
        "chunk lifecycle from parsing to search results",
        "how indexer calls chunker then storage then embedder",
        "connection between server.py tools and searcher methods",
        "how CLI commands wire up storage indexer searcher",
        "relationship between VectorStore and HybridSearcher",
        "how file watcher triggers re-indexing via indexer",
        "flow from search_fts in storage to search in HybridSearcher",
        "how embedder output goes into vector_store",
        "how get_context calls search then assembles results",
    ],

    # ── Tier 7: Bug investigation / debugging ────────────────────────────
    "Debugging": [
        "why would FTS5 search return zero results",
        "why might get_context be slow",
        "what happens if tree-sitter fails to parse a file",
        "what if the vector store file is corrupted",
        "what if a file is deleted while indexing",
        "error handling in embed_batch",
        "what happens when token_count is None in get_context",
        "race condition in file watcher callback",
        "database locked error in concurrent access",
        "memory usage with large codebases",
    ],

    # ── Tier 8: Implementation planning ──────────────────────────────────
    "Planning": [
        "add a new language to the chunker",
        "add a new MCP tool for code navigation",
        "implement semantic code search with reranking",
        "add support for multiple projects in one index",
        "implement chunk deduplication across files",
        "add caching layer for frequent queries",
        "implement streaming search results",
        "add support for searching by file type",
        "implement code change impact analysis",
        "add telemetry and usage statistics",
    ],

    # ── Tier 9: Architecture / design review ─────────────────────────────
    "Architecture": [
        "review the overall module dependency graph",
        "evaluate the storage schema design decisions",
        "assess the hybrid search ranking strategy",
        "review error handling patterns across the codebase",
        "evaluate the embedding pipeline performance",
        "review the Docker deployment architecture",
        "assess the testing strategy and coverage",
        "review the CLI argument parsing design",
        "evaluate the file watching and sync strategy",
        "review the compression and storage tradeoffs",
    ],

    # ── Tier 10: Broad / exploratory (hardest) ───────────────────────────
    "Exploratory": [
        "give me a complete overview of this project",
        "what are all the external dependencies and why",
        "summarize every module and its responsibility",
        "list all configuration options and defaults",
        "what are the main performance bottlenecks",
        "what test coverage exists and what is missing",
        "how would I contribute a new feature to this project",
        "what security considerations exist in this codebase",
        "compare the search approaches used here",
        "what would need to change to support a REST API",
    ],
}


def estimate_traditional_tokens(storage: Storage, query: str) -> int:
    """Estimate tokens for the traditional Grep+Read approach.

    Simulates what Claude Code does without Arrow:
    1. Glob to find relevant files
    2. Grep for keywords
    3. Read matching files (often entire files)

    We estimate by finding files that match query keywords and summing their
    chunk tokens (which approximates reading those files).
    """
    words = [w.lower() for w in query.split() if len(w) > 2]

    # Search FTS to find which files would be relevant
    fts_results = storage.search_fts(query, limit=100)
    if not fts_results:
        # Fallback: assume at least 2-3 files would be read
        return 3000

    # Get unique file IDs from matching chunks
    chunk_ids = [cid for cid, _ in fts_results]
    chunks = storage.get_chunks_by_ids(chunk_ids)
    file_ids = list({c.file_id for c in chunks})

    conn = storage.conn

    # For each matching file, sum ALL chunk tokens (simulating reading entire file)
    total_tokens = 0
    for fid in file_ids:
        file_chunks = conn.execute(
            "SELECT token_count FROM chunks WHERE file_id = ?", (fid,)
        ).fetchall()
        for row in file_chunks:
            total_tokens += (row[0] or 50)

    # Add overhead for grep output formatting, file paths, etc.
    total_tokens += len(file_ids) * 20

    # For broad queries, more files get read
    broad_keywords = {"overview", "review", "all", "every", "complete", "summarize",
                      "list", "architecture", "project", "compare"}
    if any(w in broad_keywords for w in words):
        # Broad queries typically read many more files
        all_files = conn.execute(
            "SELECT COUNT(*) FROM files"
        ).fetchone()[0]
        total_tokens = max(total_tokens, total_tokens * min(all_files // 3, 5))

    return total_tokens


def run_benchmark(target_path: str):
    """Run the full benchmark suite."""
    db_path = tempfile.mktemp(suffix=".db")
    storage = Storage(db_path)
    indexer = Indexer(storage)

    print(f"Indexing {target_path}...")
    result = indexer.index_codebase(target_path)
    print(f"  {result['files_indexed']} files, {result['chunks_created']} chunks\n")

    searcher = HybridSearcher(storage)

    # Warm up
    searcher.get_context("test", token_budget=4000)

    total_queries = sum(len(qs) for qs in QUERIES.values())
    print(f"Running {total_queries} queries across {len(QUERIES)} complexity tiers\n")
    print("=" * 100)

    grand_arrow_tokens = 0
    grand_trad_tokens = 0
    grand_arrow_time = 0.0
    tier_results = []

    for tier_name, queries in QUERIES.items():
        tier_arrow_tok = 0
        tier_trad_tok = 0
        tier_time = 0.0
        query_details = []

        for query in queries:
            start = time.perf_counter()
            ctx = searcher.get_context(query, token_budget=4000)
            elapsed = time.perf_counter() - start

            arrow_tok = ctx["tokens_used"]
            trad_tok = estimate_traditional_tokens(storage, query)

            tier_arrow_tok += arrow_tok
            tier_trad_tok += trad_tok
            tier_time += elapsed

            savings = (1 - arrow_tok / max(trad_tok, 1)) * 100
            query_details.append({
                "query": query,
                "arrow_tokens": arrow_tok,
                "trad_tokens": trad_tok,
                "time_ms": elapsed * 1000,
                "savings_pct": savings,
            })

        tier_savings = (1 - tier_arrow_tok / max(tier_trad_tok, 1)) * 100
        tier_results.append({
            "tier": tier_name,
            "queries": len(queries),
            "arrow_tokens": tier_arrow_tok,
            "trad_tokens": tier_trad_tok,
            "time_ms": tier_time * 1000,
            "savings_pct": tier_savings,
            "details": query_details,
        })

        grand_arrow_tokens += tier_arrow_tok
        grand_trad_tokens += tier_trad_tok
        grand_arrow_time += tier_time

        avg_ms = (tier_time / len(queries)) * 1000
        print(f"  {tier_name:20s}  {len(queries):3d} queries  "
              f"Arrow: {tier_arrow_tok:7,d} tok  "
              f"Trad: {tier_trad_tok:8,d} tok  "
              f"Savings: {tier_savings:5.1f}%  "
              f"Avg: {avg_ms:.1f}ms/q")

    print("=" * 100)
    grand_savings = (1 - grand_arrow_tokens / max(grand_trad_tokens, 1)) * 100
    avg_ms = (grand_arrow_time / total_queries) * 1000
    print(f"  {'TOTAL':20s}  {total_queries:3d} queries  "
          f"Arrow: {grand_arrow_tokens:7,d} tok  "
          f"Trad: {grand_trad_tokens:8,d} tok  "
          f"Savings: {grand_savings:5.1f}%  "
          f"Avg: {avg_ms:.1f}ms/q")
    print(f"\n  Total Arrow time: {grand_arrow_time*1000:.0f}ms "
          f"({grand_arrow_time*1000/total_queries:.1f}ms per query)")

    # Save detailed results as JSON
    output = {
        "target": str(target_path),
        "total_queries": total_queries,
        "grand_arrow_tokens": grand_arrow_tokens,
        "grand_trad_tokens": grand_trad_tokens,
        "grand_savings_pct": grand_savings,
        "total_time_ms": grand_arrow_time * 1000,
        "avg_time_ms": avg_ms,
        "tiers": tier_results,
    }
    results_path = Path(__file__).parent / "comparison_results.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Detailed results saved to {results_path}")

    storage.close()
    os.unlink(db_path)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent.parent / "src" / "arrow"
    )
    run_benchmark(target)
