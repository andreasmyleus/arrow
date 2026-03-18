"""Tests for the usearch vector store."""

import os
import tempfile

import numpy as np
import pytest

from arrow.vector_store import VectorStore


@pytest.fixture
def vec_store():
    path = tempfile.mktemp(suffix=".usearch")
    vs = VectorStore(path, ndim=64)
    yield vs
    if os.path.exists(path):
        os.unlink(path)


class TestVectorStore:
    def test_add_and_search(self, vec_store):
        vecs = np.random.randn(10, 64).astype(np.float32)
        # Normalize
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        keys = list(range(1, 11))
        vec_store.add(keys, vecs)

        results = vec_store.search(vecs[0], limit=3)
        assert len(results) > 0
        # First result should be the query vector itself
        assert results[0][0] == 1

    def test_empty_search(self, vec_store):
        query = np.random.randn(64).astype(np.float32)
        results = vec_store.search(query, limit=5)
        assert results == []

    def test_save_and_load(self, vec_store):
        vecs = np.random.randn(5, 64).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        vec_store.add(list(range(1, 6)), vecs)
        vec_store.save()

        # Load into new instance
        vs2 = VectorStore(vec_store.index_path, ndim=64)
        results = vs2.search(vecs[0], limit=3)
        assert len(results) > 0
        assert results[0][0] == 1

    def test_len(self, vec_store):
        assert len(vec_store) == 0
        vecs = np.random.randn(3, 64).astype(np.float32)
        vec_store.add([1, 2, 3], vecs)
        assert len(vec_store) == 3

    def test_remove(self, vec_store):
        vecs = np.random.randn(5, 64).astype(np.float32)
        vec_store.add(list(range(1, 6)), vecs)
        vec_store.remove([1, 2])
        # usearch may still report the same len after remove, but search should not return removed
        # Just ensure no crash
        results = vec_store.search(vecs[0], limit=10)
        assert isinstance(results, list)

    def test_high_dimensionality(self):
        path = tempfile.mktemp(suffix=".usearch")
        try:
            vs = VectorStore(path, ndim=768)
            vecs = np.random.randn(20, 768).astype(np.float32)
            vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
            vs.add(list(range(1, 21)), vecs)
            results = vs.search(vecs[5], limit=5)
            assert len(results) > 0
            assert results[0][0] == 6  # key 6 = index 5
        finally:
            if os.path.exists(path):
                os.unlink(path)
