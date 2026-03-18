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
    project_name: str = ""


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[int, float]]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion."""
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

    def _resolve_project_id(self, project: Optional[str]) -> Optional[int]:
        """Resolve a project name to a project_id. Returns None for all-projects."""
        if project is None:
            return None
        proj = self.storage.get_project_by_name(project)
        return proj.id if proj else None

    def search(
        self,
        query: str,
        limit: int = 10,
        fts_limit: int = 50,
        vec_limit: int = 50,
        project_id: Optional[int] = None,
        frecency_boost: bool = False,
        exclude_chunk_ids: Optional[set[int]] = None,
    ) -> list[SearchResult]:
        """Hybrid search combining BM25 and vector similarity.

        Args:
            query: Search query.
            limit: Max results to return.
            fts_limit: Max FTS candidates.
            vec_limit: Max vector candidates.
            project_id: Optional project filter. None = search all projects.
        """
        ranked_lists = []

        # BM25 search via FTS5 (project-scoped if specified)
        fts_results = self.storage.search_fts(
            query, limit=fts_limit, project_id=project_id
        )
        if fts_results:
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
                # Over-fetch for project filtering
                fetch_limit = vec_limit * 3 if project_id else vec_limit
                vec_results = self.vector_store.search(
                    query_vec, limit=fetch_limit
                )
                if vec_results and project_id is not None:
                    # Post-filter by project
                    chunk_ids = [cid for cid, _ in vec_results]
                    chunks = self.storage.get_chunks_by_ids(chunk_ids)
                    valid_ids = {
                        c.id for c in chunks if c.project_id == project_id
                    }
                    vec_results = [
                        (cid, dist) for cid, dist in vec_results
                        if cid in valid_ids
                    ][:vec_limit]
                if vec_results:
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

        # Filter out already-sent chunks (conversation awareness)
        if exclude_chunk_ids:
            fused = [
                (cid, s) for cid, s in fused
                if cid not in exclude_chunk_ids
            ]

        # Apply frecency boost
        if frecency_boost:
            frecency = self.storage.get_frecency_scores(
                project_id=project_id
            )
            if frecency:
                # Pre-fetch chunk->file mapping for boost
                boost_ids = [cid for cid, _ in fused[:limit * 2]]
                boost_chunks = {
                    c.id: c.file_id
                    for c in self.storage.get_chunks_by_ids(
                        boost_ids
                    )
                }
                boosted = []
                for cid, score in fused:
                    fid = boost_chunks.get(cid)
                    if fid and fid in frecency:
                        # Boost: up to 30% increase
                        boost = min(frecency[fid] * 0.05, 0.3)
                        score = score * (1.0 + boost)
                    boosted.append((cid, score))
                fused = sorted(
                    boosted, key=lambda x: x[1], reverse=True
                )

        # Batch fetch chunks and files to avoid N+1 queries
        top = fused[:limit]
        chunk_ids = [cid for cid, _ in top]
        chunks_map = {
            c.id: c for c in self.storage.get_chunks_by_ids(chunk_ids)
        }

        # Batch fetch files
        file_ids = list({c.file_id for c in chunks_map.values()})
        files_map = {}
        for fid in file_ids:
            rec = self.storage.get_file_by_id(fid)
            if rec:
                files_map[fid] = rec

        # Build project name lookup
        project_names: dict[int, str] = {}
        project_ids_seen = {
            c.project_id for c in chunks_map.values() if c.project_id
        }
        for pid in project_ids_seen:
            proj = self.storage.get_project(pid)
            if proj:
                project_names[pid] = proj.name

        results = []
        for chunk_id, score in top:
            chunk = chunks_map.get(chunk_id)
            if chunk is None:
                continue

            file_rec = files_map.get(chunk.file_id)
            file_path = file_rec.path if file_rec else ""
            proj_name = project_names.get(chunk.project_id, "")

            # Use content_text (plain text) if available
            if chunk.content_text:
                content = chunk.content_text
            else:
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
                    project_name=proj_name,
                )
            )

        return results

    def estimate_budget(
        self, query: str, project_id: Optional[int] = None
    ) -> int:
        """Estimate optimal token budget based on query complexity.

        Simple symbol lookups need ~500 tokens. Broad architectural
        questions need ~8000+. Uses FTS hit count as a proxy for scope.
        """
        hit_count = self.storage.count_fts_hits(query, project_id=project_id)
        word_count = len(query.split())

        # Heuristics for budget estimation
        if hit_count <= 2 and word_count <= 3:
            return 500   # Simple symbol lookup
        if hit_count <= 5 and word_count <= 4:
            return 1500  # Focused question
        if hit_count <= 15:
            return 3000  # Moderate scope
        if hit_count <= 30:
            return 5000  # Broad question
        if hit_count <= 60:
            return 8000  # Architectural review
        return 12000     # Very broad / exploratory

    def get_context(
        self, query: str, token_budget: int = 8000,
        project_id: Optional[int] = None,
        exclude_chunk_ids: Optional[set[int]] = None,
        frecency_boost: bool = False,
    ) -> dict:
        """Retrieve the most relevant code fitting within a token budget.

        Args:
            query: What to search for.
            token_budget: Max tokens to return.
            project_id: Optional project filter. None = all projects.
            exclude_chunk_ids: Chunk IDs to skip (already sent).
            frecency_boost: Boost recently accessed files.
        """
        results = self.search(
            query, limit=50, project_id=project_id,
            exclude_chunk_ids=exclude_chunk_ids,
            frecency_boost=frecency_boost,
        )

        if not results:
            return {
                "query": query,
                "token_budget": token_budget,
                "tokens_used": 0,
                "chunks": [],
            }

        HEADER_OVERHEAD = 15
        selected = []
        tokens_used = 0

        for result in results:
            chunk_tokens = (result.chunk.token_count or 0) + HEADER_OVERHEAD

            if tokens_used + chunk_tokens > token_budget:
                remaining = token_budget - tokens_used - HEADER_OVERHEAD
                if remaining > 100:
                    content = result.content
                    total_chars = len(content)
                    total_toks = result.chunk.token_count or 1
                    chars_per_tok = total_chars / total_toks
                    target_chars = int(remaining * chars_per_tok)

                    truncated = content[:target_chars]
                    last_nl = truncated.rfind("\n")
                    if last_nl > 0:
                        truncated = truncated[:last_nl]

                    if truncated.strip():
                        est_tokens = int(len(truncated) / chars_per_tok) + HEADER_OVERHEAD
                        selected.append({
                            "file": result.file_path,
                            "project": result.project_name,
                            "name": result.chunk.name,
                            "kind": result.chunk.kind,
                            "lines": f"{result.chunk.start_line}-{result.chunk.end_line}",
                            "content": truncated,
                            "truncated": True,
                            "tokens": est_tokens,
                        })
                        tokens_used += est_tokens
                break

            selected.append({
                "file": result.file_path,
                "project": result.project_name,
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
