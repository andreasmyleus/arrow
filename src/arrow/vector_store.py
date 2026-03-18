"""Vector store using usearch for fast approximate nearest neighbor search."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from usearch.index import Index, ScalarKind

logger = logging.getLogger(__name__)


class VectorStore:
    """usearch-based vector index for embedding search."""

    def __init__(self, index_path: str | Path, ndim: int = 768):
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.ndim = ndim
        self._index: Optional[Index] = None

    @property
    def index(self) -> Index:
        if self._index is None:
            self._index = Index(
                ndim=self.ndim,
                metric="cos",
                dtype=ScalarKind.F16,  # Half-precision for memory efficiency
            )
            # Load existing index if available
            if self.index_path.exists():
                try:
                    self._index.load(str(self.index_path))
                    logger.info(
                        "Loaded vector index: %d vectors", len(self._index)
                    )
                except Exception:
                    logger.warning("Could not load index, starting fresh")
        return self._index

    def add(self, keys: list[int], vectors: np.ndarray) -> None:
        """Add vectors to the index.

        Args:
            keys: List of chunk IDs.
            vectors: (N, ndim) array of embeddings.
        """
        keys_array = np.array(keys, dtype=np.uint64)
        self.index.add(keys_array, vectors)

    def remove(self, keys: list[int]) -> None:
        """Remove vectors from the index."""
        for key in keys:
            try:
                self.index.remove(int(key))
            except Exception:
                pass  # Key may not exist

    def search(
        self, query_vector: np.ndarray, limit: int = 50
    ) -> list[tuple[int, float]]:
        """Search for nearest neighbors.

        Returns list of (chunk_id, distance) tuples, sorted by similarity.
        """
        if len(self.index) == 0:
            return []

        results = self.index.search(query_vector, limit)
        return [
            (int(results.keys[i]), float(results.distances[i]))
            for i in range(len(results.keys))
        ]

    def save(self) -> None:
        """Persist index to disk."""
        if self._index is not None and len(self._index) > 0:
            self._index.save(str(self.index_path))
            logger.info("Saved vector index: %d vectors", len(self._index))

    def __len__(self) -> int:
        return len(self.index) if self._index is not None else 0
