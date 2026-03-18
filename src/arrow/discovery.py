""".gitignore-aware file discovery."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterator

# Default patterns to always ignore
DEFAULT_IGNORE = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".tox",
    ".venv",
    "venv",
    ".env",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.o",
    "*.a",
    "*.class",
    "*.jar",
    "*.war",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.wasm",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.bmp",
    "*.webp",
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.avi",
    "*.mov",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.bz2",
    "*.xz",
    "*.7z",
    "*.rar",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
}

# Max file size to index (1MB)
MAX_FILE_SIZE = 1_048_576


def parse_gitignore(gitignore_path: Path) -> list[str]:
    """Parse a .gitignore file and return list of patterns."""
    patterns = []
    if not gitignore_path.exists():
        return patterns
    for line in gitignore_path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _should_ignore(
    name: str,
    rel_path: str,
    is_dir: bool,
    ignore_patterns: list[str],
) -> bool:
    """Check if a file/dir should be ignored."""
    # Check default ignores
    for pattern in DEFAULT_IGNORE:
        if fnmatch.fnmatch(name, pattern):
            return True

    # Check gitignore patterns
    for pattern in ignore_patterns:
        negated = pattern.startswith("!")
        if negated:
            continue  # Skip negation for simplicity in v0.1

        # Normalize pattern
        p = pattern.rstrip("/")

        # Directory-only pattern
        if pattern.endswith("/") and not is_dir:
            continue

        # Match against name and relative path
        if fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel_path, p):
            return True
        # Handle patterns with /
        if "/" in p:
            if fnmatch.fnmatch(rel_path, p):
                return True
        else:
            if fnmatch.fnmatch(name, p):
                return True

    return False


def discover_files(root: str | Path) -> Iterator[Path]:
    """Walk directory tree, respecting .gitignore and default ignores.

    Yields absolute paths to indexable files.
    """
    root = Path(root).resolve()
    gitignore_patterns = parse_gitignore(root / ".gitignore")

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        current = Path(dirpath)
        rel_dir = current.relative_to(root)

        # Filter directories in-place to prevent descending into ignored dirs
        dirnames[:] = [
            d
            for d in dirnames
            if not _should_ignore(
                d, str(rel_dir / d), is_dir=True, ignore_patterns=gitignore_patterns
            )
        ]

        # Parse nested .gitignore files
        nested_gitignore = current / ".gitignore"
        if nested_gitignore.exists() and current != root:
            gitignore_patterns = gitignore_patterns + parse_gitignore(nested_gitignore)

        for filename in filenames:
            filepath = current / filename
            rel_path = str(filepath.relative_to(root))

            if _should_ignore(
                filename, rel_path, is_dir=False, ignore_patterns=gitignore_patterns
            ):
                continue

            # Skip files that are too large
            try:
                if filepath.stat().st_size > MAX_FILE_SIZE:
                    continue
                if filepath.stat().st_size == 0:
                    continue
            except OSError:
                continue

            # Skip binary files (quick check)
            try:
                with open(filepath, "rb") as f:
                    sample = f.read(512)
                if b"\x00" in sample:
                    continue
            except OSError:
                continue

            yield filepath
