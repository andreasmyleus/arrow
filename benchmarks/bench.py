"""Benchmark suite for Arrow MCP server."""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arrow.hasher import hash_content, hash_file
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
    print(f"Hashing:     {n} x 10KB in {elapsed:.3f}s ({throughput:.0f} MB/s)")


def bench_token_counting(n=1000):
    """Benchmark tiktoken token counting."""
    text = "def hello_world():\n    return 'Hello, World!'\n" * 20
    start = time.perf_counter()
    for _ in range(n):
        count_tokens(text)
    elapsed = time.perf_counter() - start
    print(f"Token count: {n} x ~1KB in {elapsed:.3f}s ({n/elapsed:.0f} ops/s)")


def bench_indexing(target_path: str):
    """Benchmark indexing a codebase."""
    db_path = tempfile.mktemp(suffix=".db")
    storage = Storage(db_path)
    indexer = Indexer(storage)

    # First index
    start = time.perf_counter()
    result = indexer.index_codebase(target_path)
    elapsed = time.perf_counter() - start
    print(
        f"Indexing:     {result['files_indexed']} files, "
        f"{result['chunks_created']} chunks in {elapsed:.3f}s "
        f"({result['files_indexed']/max(elapsed,0.001):.0f} files/s)"
    )

    # Incremental (no changes)
    start = time.perf_counter()
    result2 = indexer.index_codebase(target_path)
    elapsed2 = time.perf_counter() - start
    print(
        f"Incremental: {result2['files_scanned']} files scanned, "
        f"0 re-indexed in {elapsed2:.3f}s"
    )

    return storage, db_path


def bench_search(storage: Storage, queries: list[str]):
    """Benchmark FTS5 search."""
    searcher = HybridSearcher(storage)

    # Warm up
    searcher.search("test", limit=5)

    for query in queries:
        start = time.perf_counter()
        results = searcher.search(query, limit=10)
        elapsed = time.perf_counter() - start
        print(f"Search:      '{query}' -> {len(results)} results in {elapsed*1000:.1f}ms")


def bench_get_context(storage: Storage):
    """Benchmark get_context with different budgets."""
    searcher = HybridSearcher(storage)

    for budget in [2000, 4000, 8000, 16000]:
        start = time.perf_counter()
        ctx = searcher.get_context("main function entry point", token_budget=budget)
        elapsed = time.perf_counter() - start
        print(
            f"get_context: budget={budget:5d} -> "
            f"{ctx['tokens_used']:5d} tokens, "
            f"{len(ctx['chunks'])} chunks in {elapsed*1000:.1f}ms"
        )


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent.parent / "src" / "arrow"
    )
    print(f"Benchmarking against: {target}")
    print("=" * 60)

    bench_hashing()
    bench_token_counting()
    print()

    storage, db_path = bench_indexing(target)
    print()

    bench_search(storage, [
        "index",
        "storage database",
        "function definition",
        "import export",
        "hash content",
    ])
    print()

    bench_get_context(storage)

    storage.close()
    os.unlink(db_path)
    print("\nDone!")


if __name__ == "__main__":
    main()
