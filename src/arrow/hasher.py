"""xxHash3-128 content hashing for incremental indexing."""

from __future__ import annotations

import xxhash


def hash_content(content: str | bytes) -> str:
    """Hash file content using xxHash3-128. Returns hex string."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return xxhash.xxh3_128(content).hexdigest()


def hash_file(path: str) -> str:
    """Hash a file's content. Reads in 64KB chunks for memory efficiency."""
    h = xxhash.xxh3_128()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
