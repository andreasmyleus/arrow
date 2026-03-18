"""Benchmark suite for Arrow MCP server."""

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arrow.hasher import hash_content
from arrow.indexer import Indexer, count_tokens
from arrow.search import HybridSearcher
from arrow.storage import Storage


def bench_hashing(n=10000):
    """Benchmark xxHash3 content hashing."""
    data = "x" * 10000
    start = time.perf_counter()
    for _ in range(n):
        hash_content(data)
    elapsed = time.perf_counter() - start
    throughput = (n * len(data)) / elapsed / 1e6
    print(f"  Hashing:       {n:,} x 10KB in {elapsed:.3f}s ({throughput:,.0f} MB/s)")


def bench_token_counting(n=1000):
    """Benchmark tiktoken token counting."""
    text = "def hello_world():\n    return 'Hello, World!'\n" * 20
    start = time.perf_counter()
    for _ in range(n):
        count_tokens(text)
    elapsed = time.perf_counter() - start
    print(f"  Token count:   {n:,} x ~1KB in {elapsed:.3f}s ({n/elapsed:,.0f} ops/s)")


def bench_indexing(target_path: str):
    """Benchmark indexing a codebase."""
    db_path = tempfile.mktemp(suffix=".db")
    storage = Storage(db_path)
    indexer = Indexer(storage)

    # First index
    start = time.perf_counter()
    result = indexer.index_codebase(target_path)
    elapsed = time.perf_counter() - start
    files = result["files_indexed"]
    chunks = result["chunks_created"]
    print(
        f"  Initial index: {files} files, "
        f"{chunks} chunks in {elapsed:.3f}s "
        f"({files/max(elapsed,0.001):.0f} files/s)"
    )

    # Incremental (no changes)
    start = time.perf_counter()
    result2 = indexer.index_codebase(target_path)
    elapsed2 = time.perf_counter() - start
    print(
        f"  Incremental:   {result2['files_scanned']} files scanned, "
        f"0 re-indexed in {elapsed2*1000:.1f}ms"
    )

    return storage, db_path


def bench_search(storage: Storage, queries: list[str]):
    """Benchmark FTS5 search with latency percentiles."""
    searcher = HybridSearcher(storage)

    # Warm up
    searcher.search("test", limit=5)

    latencies = []
    result_counts = []
    for query in queries:
        start = time.perf_counter()
        results = searcher.search(query, limit=10)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        result_counts.append(len(results))

    p50 = statistics.median(latencies)
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]
    avg_results = statistics.mean(result_counts)

    print(f"  Search ({len(queries)} queries):")
    print(f"    p50 latency: {p50:.2f}ms")
    print(f"    p99 latency: {p99:.2f}ms")
    print(f"    avg results: {avg_results:.1f} per query")

    for query in queries[:3]:
        start = time.perf_counter()
        results = searcher.search(query, limit=10)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"    '{query}' -> {len(results)} results in {elapsed:.2f}ms")

    return latencies


def bench_get_context(storage: Storage):
    """Benchmark get_context with different budgets."""
    searcher = HybridSearcher(storage)

    # Warm up
    searcher.get_context("test", token_budget=2000)

    queries = [
        "main function entry point",
        "database storage operations",
        "search and retrieval",
        "how does indexing work",
        "authentication and authorization",
    ]

    print(f"  get_context ({len(queries)} queries x 4 budgets):")
    for budget in [2000, 4000, 8000, 16000]:
        latencies = []
        tokens_used = []
        chunks_returned = []
        for query in queries:
            start = time.perf_counter()
            ctx = searcher.get_context(query, token_budget=budget)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            tokens_used.append(ctx["tokens_used"])
            chunks_returned.append(ctx["chunks_returned"])

        avg_lat = statistics.mean(latencies)
        avg_tok = statistics.mean(tokens_used)
        avg_chunks = statistics.mean(chunks_returned)
        fill_rate = (avg_tok / budget) * 100

        print(
            f"    budget={budget:5d} -> "
            f"avg {avg_tok:5.0f} tok ({fill_rate:.0f}% fill), "
            f"{avg_chunks:.1f} chunks, "
            f"{avg_lat:.2f}ms"
        )


def bench_budget_estimation(storage: Storage):
    """Benchmark the auto budget estimator."""
    searcher = HybridSearcher(storage)

    test_queries = [
        ("add", "symbol"),
        ("search_fts method", "method"),
        ("how does hybrid search work", "how-does"),
        ("review the overall architecture and module design", "architecture"),
        ("give me a complete overview of everything", "exploratory"),
    ]

    print("  Auto budget estimation:")
    for query, qtype in test_queries:
        budget = searcher.estimate_budget(query)
        print(f"    '{query}' ({qtype}) -> {budget:,d} tokens")


def collect_index_stats(storage: Storage):
    """Collect and display index statistics."""
    conn = storage.conn

    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    total_symbols = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    total_imports = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0]

    chunk_tokens = conn.execute(
        "SELECT SUM(token_count), AVG(token_count), "
        "MIN(token_count), MAX(token_count) FROM chunks"
    ).fetchone()

    chunks_per_file = conn.execute(
        "SELECT AVG(cnt) FROM "
        "(SELECT COUNT(*) as cnt FROM chunks GROUP BY file_id)"
    ).fetchone()[0]

    # Language distribution
    langs = conn.execute(
        "SELECT language, COUNT(*) FROM files "
        "WHERE language IS NOT NULL "
        "GROUP BY language ORDER BY COUNT(*) DESC"
    ).fetchall()

    # Chunk kinds
    kinds = conn.execute(
        "SELECT kind, COUNT(*) FROM chunks "
        "GROUP BY kind ORDER BY COUNT(*) DESC"
    ).fetchall()

    print("  Index contents:")
    print(f"    Files:    {total_files}")
    print(f"    Chunks:   {total_chunks}")
    print(f"    Symbols:  {total_symbols}")
    print(f"    Imports:  {total_imports}")
    print(f"    Chunks/file: {chunks_per_file:.1f} avg")
    print(f"    Tokens:   {chunk_tokens[0]:,d} total, "
          f"{chunk_tokens[1]:.0f} avg, "
          f"{chunk_tokens[2]}-{chunk_tokens[3]} range")
    if langs:
        lang_str = ", ".join(f"{l[0]}({l[1]})" for l in langs[:5])
        print(f"    Languages: {lang_str}")
    if kinds:
        kind_str = ", ".join(f"{k[0]}({k[1]})" for k in kinds[:5])
        print(f"    Chunk kinds: {kind_str}")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent.parent / "src" / "arrow"
    )
    print(f"\nArrow Benchmark Suite")
    print(f"Target: {target}")
    print("=" * 60)

    print("\n[1] Primitive Operations")
    bench_hashing()
    bench_token_counting()

    print("\n[2] Indexing")
    storage, db_path = bench_indexing(target)

    # DB size on disk
    db_size = os.path.getsize(db_path)
    print(f"  DB size:       {db_size / 1024:.0f} KB")

    print("\n[3] Index Statistics")
    collect_index_stats(storage)

    print("\n[4] Search Latency")
    bench_search(storage, [
        "index",
        "storage database",
        "function definition",
        "import export",
        "hash content",
        "search results",
        "token budget",
        "file watcher",
        "MCP server",
        "tree-sitter",
    ])

    print("\n[5] Context Assembly")
    bench_get_context(storage)

    print("\n[6] Budget Estimation")
    bench_budget_estimation(storage)

    storage.close()
    os.unlink(db_path)
    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
