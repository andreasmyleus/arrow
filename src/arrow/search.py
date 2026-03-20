"""Hybrid search: BM25 (FTS5) + semantic (vector) with reciprocal rank fusion."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import tiktoken

from .chunker import decompress_content
from .config import get_config
from .storage import ChunkRecord, Storage
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

# Non-code languages get a score penalty so they don't dominate search results
_NON_CODE_LANGS = {"markdown", "json", "yaml", "toml", "csv", "xml"}

_TEST_PATH_MARKERS = ("test_", "_test.", "tests/", "__tests__/", "spec/", "/test/")

# Words to ignore when matching query terms against file names
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "how", "what", "where", "when", "who", "which", "that", "this",
    "for", "from", "with", "without", "about", "into", "through",
    "in", "on", "at", "to", "of", "by", "as", "if", "then",
    "all", "each", "every", "any", "some", "no", "more", "most",
    "it", "its", "my", "your", "our", "their", "his", "her",
    "def", "class", "function", "method", "file", "code",
    "find", "show", "get", "list", "search", "look", "use", "used",
})


def _extract_query_concepts(query: str) -> list[str]:
    """Extract meaningful concept terms from a query, filtering stop words.

    Returns lowercase terms of 3+ characters that aren't stop words.
    Also splits snake_case tokens into sub-terms.
    """
    raw_tokens = re.split(r'[^a-zA-Z0-9_]+', query.lower())
    concepts = []
    for token in raw_tokens:
        if len(token) < 3 or token in _STOP_WORDS:
            continue
        concepts.append(token)
        # Also add sub-parts of snake_case tokens
        if '_' in token:
            for part in token.split('_'):
                if len(part) >= 3 and part not in _STOP_WORDS and part != token:
                    concepts.append(part)
    return concepts


def _filename_match_boost(path: str, concepts: list[str]) -> float:
    """Score how well a file name matches query concepts.

    Returns a boost multiplier:
    - 1.0 = no match
    - 2.0 = file stem matches a concept exactly (e.g. query "frecency" -> frecency.py)
    - 1.5 = file stem contains a concept (e.g. query "vector" -> vector_store.py)
    """
    if not concepts:
        return 1.0

    stem = os.path.splitext(os.path.basename(path))[0].lower()

    # Exact stem match: "frecency" query -> frecency.py
    if stem in concepts:
        return 2.0

    # Stem contains a concept: "vector" query -> vector_store.py
    for concept in concepts:
        if concept in stem:
            return 1.5

    return 1.0


def _is_test_path(path_lower: str) -> bool:
    """Check if a file path looks like a test file."""
    return any(m in path_lower for m in _TEST_PATH_MARKERS)

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
    k: int = 20,
) -> list[tuple[int, float]]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    A lower k value (default 20, down from the standard 60) gives more
    weight to top-ranked results, improving precision when BM25 and
    vector search agree on what's most relevant.
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
        # Build a set of chunk IDs that BM25 found (for exact-match bonus)
        bm25_hit_ids: set[int] = set()
        if fts_results:
            bm25_ranked = [(cid, -score) for cid, score in fts_results]
            bm25_hit_ids = {cid for cid, _ in bm25_ranked}
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

        # Reciprocal rank fusion (k=20 for sharper top-rank differentiation)
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

        # --- Scoring adjustments: file-name boost, BM25 bonus, penalties ---
        # Extract meaningful concepts from the query for file-name matching
        query_concepts = _extract_query_concepts(query)

        adjust_ids = [cid for cid, _ in fused[:limit * 3]]
        if adjust_ids:
            adjust_chunks = {
                c.id: c.file_id
                for c in self.storage.get_chunks_by_ids(adjust_ids)
            }
            adjust_files = {}
            for fid in set(adjust_chunks.values()):
                rec = self.storage.get_file_by_id(fid)
                if rec:
                    adjust_files[fid] = rec

            query_mentions_test = any(
                t in ("test", "tests", "testing", "spec")
                for t in query_concepts
            )

            adjusted = []
            for cid, score in fused:
                fid = adjust_chunks.get(cid)
                frec = adjust_files.get(fid) if fid else None
                if frec:
                    path_lower = frec.path.lower()

                    # Non-code penalty
                    if frec.language in _NON_CODE_LANGS:
                        score = score * get_config().search.non_code_penalty

                    # File-name match boost (uses concept extraction
                    # instead of raw query terms for better matching)
                    name_boost = _filename_match_boost(path_lower, query_concepts)
                    score = score * name_boost

                    # Exact-match bonus: chunks found by BM25 (keyword match)
                    # get a 20% boost — they contain the literal query terms
                    if cid in bm25_hit_ids:
                        score = score * 1.2

                    # Test file penalty when query isn't about tests
                    if not query_mentions_test and _is_test_path(path_lower):
                        score = score * 0.7

                adjusted.append((cid, score))
            fused = sorted(adjusted, key=lambda x: x[1], reverse=True)

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
        MAX_CHUNKS_PER_FILE = 3
        selected = []
        tokens_used = 0
        file_chunk_counts: dict[str, int] = {}

        for result in results:
            # Enforce per-file diversity cap
            fp = result.file_path
            if file_chunk_counts.get(fp, 0) >= MAX_CHUNKS_PER_FILE:
                continue

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
                        file_chunk_counts[fp] = file_chunk_counts.get(fp, 0) + 1
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
            file_chunk_counts[fp] = file_chunk_counts.get(fp, 0) + 1

        return {
            "query": query,
            "token_budget": token_budget,
            "tokens_used": tokens_used,
            "chunks_searched": len(results),
            "chunks_returned": len(selected),
            "chunks": selected,
        }
