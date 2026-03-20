"""Hybrid search: BM25 (FTS5) + semantic (vector) with reciprocal rank fusion."""

from __future__ import annotations

import logging
import os
import re as _re
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

# Keywords that signal the user wants documentation, not source code
_DOC_QUERY_KEYWORDS = {
    "tool", "tools", "list", "expose", "api", "usage", "readme",
    "documentation", "docs", "doc", "overview", "getting started",
    "install", "installation", "guide", "reference", "help",
    "commands", "options", "features", "available", "supported",
    "endpoints", "configuration", "config",
}

_DOC_QUERY_PHRASES = (
    "what does", "how to", "getting started", "mcp tool", "mcp server",
    "what mcp", "list of", "how do i", "what are",
)

_DOC_PATH_MARKERS = ("readme", "changelog", "contributing", "guide", "docs/")


def _is_doc_query(query_lower: str) -> bool:
    """Check if a query is asking about documentation/overview information."""
    words = set(query_lower.split())
    if words & _DOC_QUERY_KEYWORDS:
        return True
    for phrase in _DOC_QUERY_PHRASES:
        if phrase in query_lower:
            return True
    return False


def _is_doc_path(path_lower: str) -> bool:
    """Check if a file path looks like documentation."""
    return any(m in path_lower for m in _DOC_PATH_MARKERS)


# --- Precision filtering constants ---
# Results scoring below this fraction of the top result's score are dropped.
_MIN_SCORE_RATIO = 0.4
# If a result's score drops by more than this factor vs the previous result,
# treat it as a relevance cliff and stop including results beyond that point.
_SCORE_DROP_RATIO = 0.5
# Never cut below this many results (protects very small result sets).
_MIN_RESULTS_FLOOR = 1

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
    raw_tokens = _re.split(r'[^a-zA-Z0-9_]+', query.lower())
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


def filter_by_relevance(
    scored: list[tuple[int, float]],
    min_score_ratio: float = _MIN_SCORE_RATIO,
    drop_ratio: float = _SCORE_DROP_RATIO,
    floor: int = _MIN_RESULTS_FLOOR,
) -> list[tuple[int, float]]:
    """Remove low-relevance tail from a scored result list.

    Two independent filters (whichever cuts more aggressively wins):

    1. **Minimum score ratio** — drop any result whose score is less than
       ``min_score_ratio`` of the top result's score.
    2. **Score drop-off** — if result *i*'s score is less than
       ``drop_ratio`` of result *i-1*'s score, discard result *i* and
       everything after it (a "relevance cliff").

    At least ``floor`` results are always kept regardless.

    The input list must be sorted descending by score (as returned by
    ``reciprocal_rank_fusion``).
    """
    if len(scored) <= floor:
        return scored

    top_score = scored[0][1] if scored else 0.0
    if top_score <= 0:
        return scored[:floor]

    cutoff = floor  # index up to which we keep results
    prev_score = top_score
    for i, (_cid, score) in enumerate(scored):
        if i < floor:
            prev_score = score
            continue
        # Check absolute relevance vs top result
        if score / top_score < min_score_ratio:
            break
        # Check relative drop vs previous result
        if prev_score > 0 and score / prev_score < drop_ratio:
            break
        cutoff = i + 1
        prev_score = score
    else:
        # Loop completed without break — keep everything
        cutoff = len(scored)

    return scored[:max(cutoff, floor)]


# ─── Query classification ───────────────────────────────────────────────

# File extensions and well-known filenames that indicate a targeted lookup
_FILE_PATTERN = _re.compile(
    r"\b\w+\.(py|js|ts|tsx|jsx|go|rs|java|rb|c|cpp|h|hpp|toml|yaml|yml|json"
    r"|md|txt|cfg|ini|sh|bash|sql|html|css|xml|proto|lock)\b",
    _re.IGNORECASE,
)
_WELL_KNOWN_FILES = _re.compile(
    r"\b(Dockerfile|Makefile|Jenkinsfile|Procfile|Gemfile|Rakefile"
    r"|docker-compose|\.github|\.gitignore|README|CHANGELOG|LICENSE"
    r"|pyproject|setup\.py|setup\.cfg|package\.json|tsconfig"
    r"|Cargo\.toml|go\.mod|pom\.xml|build\.gradle)\b",
    _re.IGNORECASE,
)

# Patterns suggesting a specific function/class/symbol lookup
_SYMBOL_CALL_RE = _re.compile(
    r"\b\w+\(\)"           # "authenticate()"
    r"|\bdef\s+\w+"        # "def authenticate"
    r"|\bclass\s+\w+"      # "class Storage"
    r"|\bfunction\s+\w+"   # "function handleRequest"
)

# Broad/architectural query indicators
_BROAD_INDICATORS = _re.compile(
    r"\b(how does|walk me through|architecture|patterns?|across|overview"
    r"|end.to.end|e2e|cross.cutting|review|throughout|design"
    r"|approach|strateg(?:y|ies)|workflow|pipeline)\b",
    _re.IGNORECASE,
)

# Single-concept keywords (short queries about one specific thing)
_SINGLE_CONCEPT_WORDS = frozenset({
    "docker", "dockerfile", "ci", "cd", "healthcheck", "health",
    "makefile", "readme", "changelog", "license", "setup",
    "logging", "auth", "authentication", "database", "cache",
    "caching", "deploy", "deployment", "lint", "linting", "build",
    "nginx", "redis", "postgres", "kafka", "rabbitmq", "celery",
})


@dataclass
class QueryClassification:
    """Result of classifying a search query as targeted or broad."""

    query_type: str  # "targeted" or "broad"
    confidence: float  # 0.0 to 1.0
    reason: str
    suggested_budget: int  # token budget hint
    suggested_limit: int  # search result limit hint


def classify_query(query: str) -> QueryClassification:
    """Classify a query as targeted (specific file/function) or broad (architectural).

    Targeted queries mention specific files, functions, or single concepts.
    They need small budgets (500-2000 tokens) and few results.

    Broad queries ask about patterns, architecture, or cross-cutting concerns.
    They need larger budgets (3000-6000 tokens) and more results.
    """
    words = query.split()
    word_count = len(words)
    query_lower = query.lower()

    targeted_signals = 0
    broad_signals = 0
    reasons: list[str] = []

    # Signal: mentions a filename or file extension
    if _FILE_PATTERN.search(query) or _WELL_KNOWN_FILES.search(query):
        targeted_signals += 3
        reasons.append("mentions file")

    # Signal: mentions a function/symbol explicitly
    if _SYMBOL_CALL_RE.search(query):
        targeted_signals += 2
        reasons.append("mentions symbol")

    # Signal: very short query (1-4 words) — likely about a single thing
    if word_count <= 4:
        targeted_signals += 1
        reasons.append("short query")
        # Extra boost for known single-concept words
        if any(w in _SINGLE_CONCEPT_WORDS for w in query_lower.split()):
            targeted_signals += 1
            reasons.append("single concept")

    # Signal: broad patterns/architecture language
    if _BROAD_INDICATORS.search(query):
        broad_signals += 2
        reasons.append("broad language")

    # Signal: longer queries tend to be broader
    if word_count >= 10:
        broad_signals += 1
        reasons.append("long query")

    # Signal: question with broad scope
    if word_count >= 6 and any(
        query_lower.startswith(w) for w in ("how ", "what ", "where ", "why ")
    ):
        broad_signals += 1
        reasons.append("broad question")

    # Decide classification
    reason_str = "; ".join(reasons) if reasons else "default"

    if targeted_signals > broad_signals:
        if targeted_signals >= 3:
            return QueryClassification("targeted", 0.9, reason_str, 1000, 5)
        return QueryClassification("targeted", 0.7, reason_str, 1500, 8)

    if broad_signals > targeted_signals:
        if broad_signals >= 3:
            return QueryClassification("broad", 0.9, reason_str, 6000, 30)
        return QueryClassification("broad", 0.7, reason_str, 4000, 20)

    # Ambiguous — use query length as tiebreaker
    if word_count < 6:
        return QueryClassification(
            "targeted", 0.4, "ambiguous; " + reason_str, 2000, 10,
        )
    return QueryClassification(
        "broad", 0.4, "ambiguous; " + reason_str, 3000, 20,
    )


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
        dedup_strategy: str = "penalize",
    ) -> list[SearchResult]:
        """Hybrid search combining BM25 and vector similarity.

        Args:
            query: Search query.
            limit: Max results to return.
            fts_limit: Max FTS candidates.
            vec_limit: Max vector candidates.
            project_id: Optional project filter. None = search all projects.
            exclude_chunk_ids: Chunk IDs already sent in this session.
            dedup_strategy: How to handle already-sent chunks:
                "none" - no dedup, ignore exclude_chunk_ids entirely
                "penalize" - demote already-sent chunks by 50% (default)
                "exclude" - hard-exclude already-sent chunks (legacy)
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

        # Conversation-aware dedup for already-sent chunks
        if exclude_chunk_ids and dedup_strategy != "none":
            if dedup_strategy == "exclude":
                # Legacy: hard-exclude already-sent chunks entirely
                fused = [
                    (cid, s) for cid, s in fused
                    if cid not in exclude_chunk_ids
                ]
            else:
                # "penalize" (default): demote already-sent chunks by 50%
                # so they still appear when highly relevant but rank lower
                penalty = 0.5
                fused = [
                    (cid, s * penalty) if cid in exclude_chunk_ids
                    else (cid, s)
                    for cid, s in fused
                ]
                # Re-sort after applying penalty
                fused.sort(key=lambda x: x[1], reverse=True)

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
            query_is_doc = _is_doc_query(query.lower())

            adjusted = []
            for cid, score in fused:
                fid = adjust_chunks.get(cid)
                frec = adjust_files.get(fid) if fid else None
                if frec:
                    path_lower = frec.path.lower()

                    # File-type scoring: boost or penalize based on query intent
                    if frec.language in _NON_CODE_LANGS:
                        if query_is_doc and _is_doc_path(path_lower):
                            # Doc query + doc file (README, etc.): strong boost
                            score = score * 2.5
                        elif query_is_doc and frec.language == "markdown":
                            # Doc query + any markdown file: mild boost
                            score = score * 1.3
                        else:
                            # Non-doc query: penalize non-code files as before
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

        # Precision filtering: drop low-relevance tail before materialising
        fused = filter_by_relevance(fused)

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
        self, query: str, project_id: Optional[int] = None,
        classification: Optional[QueryClassification] = None,
    ) -> tuple[int, int, QueryClassification]:
        """Estimate a token ceiling and search limit for a query.

        The token budget is a **safety ceiling**, not a fill target.
        Relevance filtering (score cutoff + cliff detection) is the
        primary control for how many results are returned.  The budget
        just prevents runaway responses.

        Returns:
            (token_ceiling, search_limit, classification)
        """
        if classification is None:
            classification = classify_query(query)

        hit_count = self.storage.count_fts_hits(query, project_id=project_id)

        if classification.query_type == "targeted":
            # Targeted: generous ceiling — relevance filter does the work
            budget = 4000
            limit = classification.suggested_limit
        else:
            # Broad: larger ceiling
            budget = 8000
            limit = classification.suggested_limit

        logger.debug(
            "Budget ceiling: query=%r type=%s confidence=%.1f ceiling=%d "
            "limit=%d hits=%d reason=%s",
            query, classification.query_type, classification.confidence,
            budget, limit, hit_count, classification.reason,
        )

        return budget, limit, classification

    def get_context(
        self, query: str, token_budget: int = 8000,
        project_id: Optional[int] = None,
        exclude_chunk_ids: Optional[set[int]] = None,
        frecency_boost: bool = False,
        dedup_strategy: str = "penalize",
        search_limit: int = 50,
    ) -> dict:
        """Retrieve the most relevant code for a query.

        Relevance-first approach:
        1. Search for candidates (already filtered by ``filter_by_relevance``
           inside ``search()``).
        2. Apply a secondary relevance floor here (score ratio vs top hit).
        3. Apply score cliff detection to stop at natural relevance gaps.
        4. The token budget is a **hard ceiling** (safety net), never a
           fill target.  No truncation is performed to squeeze more in.

        Args:
            query: What to search for.
            token_budget: Hard token ceiling (safety net, not a fill target).
            project_id: Optional project filter. None = all projects.
            exclude_chunk_ids: Chunk IDs to skip (already sent).
            frecency_boost: Boost recently accessed files.
            dedup_strategy: "none", "penalize" (default), or "exclude".
            search_limit: Max search results to consider (default 50).
        """
        results = self.search(
            query, limit=search_limit, project_id=project_id,
            exclude_chunk_ids=exclude_chunk_ids,
            frecency_boost=frecency_boost,
            dedup_strategy=dedup_strategy,
        )

        if not results:
            return {
                "query": query,
                "token_budget": token_budget,
                "tokens_used": 0,
                "chunks": [],
            }

        header_overhead = 15
        max_chunks_per_file = 3

        # --- Relevance-first filtering ---
        # The search() method already ran filter_by_relevance() on the raw
        # RRF scores.  Here we apply a second pass on materialised results
        # to catch anything that slipped through (e.g. after frecency boost
        # or penalty adjustments changed the ordering).

        top_score = results[0].score
        if top_score <= 0:
            top_score = 1.0

        # 1) Absolute relevance floor: drop anything < 40% of top score
        relevance_floor = _MIN_SCORE_RATIO  # 0.4

        # 2) Score cliff detection: stop when a result's score drops to
        #    < 50% of the *previous* result's score (big gap = irrelevant tail)
        cliff_ratio = _SCORE_DROP_RATIO  # 0.5

        relevant_results: list[SearchResult] = []
        prev_score = top_score

        for result in results:
            ratio_vs_top = result.score / top_score
            ratio_vs_prev = result.score / prev_score if prev_score > 0 else 0.0

            # Floor: below minimum relevance relative to the best result
            if ratio_vs_top < relevance_floor and len(relevant_results) >= 1:
                break

            # Cliff: sudden drop compared to the previous result
            if ratio_vs_prev < cliff_ratio and len(relevant_results) >= 1:
                break

            relevant_results.append(result)
            prev_score = result.score

        # --- Assemble output, respecting token ceiling and per-file cap ---
        selected = []
        tokens_used = 0
        file_chunk_counts: dict[str, int] = {}

        for result in relevant_results:
            file_path = result.file_path
            if file_chunk_counts.get(file_path, 0) >= max_chunks_per_file:
                continue

            chunk_tokens = (result.chunk.token_count or 0) + header_overhead

            # Token ceiling: hard stop, no truncation
            if tokens_used + chunk_tokens > token_budget:
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
            file_chunk_counts[file_path] = file_chunk_counts.get(file_path, 0) + 1

        return {
            "query": query,
            "token_budget": token_budget,
            "tokens_used": tokens_used,
            "chunks_searched": len(results),
            "chunks_returned": len(selected),
            "chunks": selected,
        }
