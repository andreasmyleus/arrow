"""Hybrid search: BM25 (FTS5) + semantic (vector) with reciprocal rank fusion."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import tiktoken

from .chunker import decompress_content
from .storage import ChunkRecord, Storage
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

_encoder: Optional[tiktoken.Encoding] = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


@dataclass
class SearchResult:
    """A search result with relevance score."""

    chunk_id: int
    score: float
    chunk: Optional[ChunkRecord] = None
    content: str = ""
    file_path: str = ""


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[int, float]]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        ranked_lists: List of ranked result lists, each containing (id, score) tuples.
        k: Smoothing constant (default 60).

    Returns:
        Merged list of (id, rrf_score), sorted by descending score.
    """
    scores: dict[int, float] = {}
    for ranked_list in ranked_lists:
        for rank, (item_id, _score) in enumerate(ranked_list):
            if item_id not in scores:
                scores[item_id] = 0.0
            scores[item_id] += 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridSearcher:
    """Combines BM25 and vector search with reciprocal rank fusion."""

    def __init__(
        self,
        storage: Storage,
        vector_store: Optional[VectorStore] = None,
        embedder=None,
    ):
        self.storage = storage
        self.vector_store = vector_store
        self.embedder = embedder

    def search(
        self, query: str, limit: int = 10, fts_limit: int = 50, vec_limit: int = 50
    ) -> list[SearchResult]:
        """Hybrid search combining BM25 and vector similarity.

        Falls back to BM25-only if vector search is unavailable.
        """
        ranked_lists = []

        # BM25 search via FTS5
        fts_results = self.storage.search_fts(query, limit=fts_limit)
        if fts_results:
            # FTS5 bm25() returns negative scores (lower = better)
            # Convert to (id, score) where higher = better
            bm25_ranked = [(cid, -score) for cid, score in fts_results]
            ranked_lists.append(bm25_ranked)

        # Vector search (if available)
        if (
            self.vector_store is not None
            and self.embedder is not None
            and self.embedder.ready
            and len(self.vector_store) > 0
        ):
            try:
                query_vec = self.embedder.embed_query(query)
                vec_results = self.vector_store.search(query_vec, limit=vec_limit)
                if vec_results:
                    # usearch returns distances (lower = better for cosine)
                    # Convert to (id, score) where higher = better
                    vec_ranked = [
                        (cid, 1.0 - dist) for cid, dist in vec_results
                    ]
                    ranked_lists.append(vec_ranked)
            except Exception:
                logger.warning("Vector search failed, using BM25 only")

        if not ranked_lists:
            return []

        # Reciprocal rank fusion
        fused = reciprocal_rank_fusion(ranked_lists)

        # Fetch chunks and build results
        results = []
        for chunk_id, score in fused[:limit]:
            chunk = self.storage.get_chunk_by_id(chunk_id)
            if chunk is None:
                continue

            file_rec = self.storage.get_file_by_id(chunk.file_id)
            file_path = file_rec.path if file_rec else ""

            try:
                content = (
                    decompress_content(chunk.content)
                    if isinstance(chunk.content, bytes)
                    else str(chunk.content)
                )
            except Exception:
                content = "<decompression error>"

            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    score=score,
                    chunk=chunk,
                    content=content,
                    file_path=file_path,
                )
            )

        return results

    def get_context(
        self, query: str, token_budget: int = 8000
    ) -> dict:
        """Retrieve the most relevant code fitting within a token budget.

        This is the main tool. Runs hybrid search → ranking → token trimming.
        Returns a dict with context chunks and metadata.
        """
        # Search with a larger pool to select from
        results = self.search(query, limit=50)

        if not results:
            return {
                "query": query,
                "token_budget": token_budget,
                "tokens_used": 0,
                "chunks": [],
            }

        # Greedily fill the token budget with highest-ranked chunks
        selected = []
        tokens_used = 0

        for result in results:
            # Build context string with scope info
            header = f"// {result.file_path}:{result.chunk.start_line}-{result.chunk.end_line}"
            chunk_text = f"{header}\n{result.content}"
            chunk_tokens = count_tokens(chunk_text)

            if tokens_used + chunk_tokens > token_budget:
                # Try to fit with truncation if it's close
                remaining = token_budget - tokens_used
                if remaining > 100:
                    # Truncate to fit
                    lines = result.content.splitlines()
                    truncated = []
                    t_tokens = count_tokens(header + "\n")
                    for line in lines:
                        line_tokens = count_tokens(line + "\n")
                        if t_tokens + line_tokens > remaining:
                            break
                        truncated.append(line)
                        t_tokens += line_tokens
                    if truncated:
                        selected.append({
                            "file": result.file_path,
                            "name": result.chunk.name,
                            "kind": result.chunk.kind,
                            "lines": f"{result.chunk.start_line}-{result.chunk.end_line}",
                            "content": "\n".join(truncated),
                            "truncated": True,
                            "tokens": t_tokens,
                        })
                        tokens_used += t_tokens
                break  # Budget full

            selected.append({
                "file": result.file_path,
                "name": result.chunk.name,
                "kind": result.chunk.kind,
                "lines": f"{result.chunk.start_line}-{result.chunk.end_line}",
                "content": result.content,
                "truncated": False,
                "tokens": chunk_tokens,
            })
            tokens_used += chunk_tokens

        return {
            "query": query,
            "token_budget": token_budget,
            "tokens_used": tokens_used,
            "chunks_searched": len(results),
            "chunks_returned": len(selected),
            "chunks": selected,
        }
