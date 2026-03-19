"""Arrow configuration — loads from ~/.arrow/config.toml with sensible defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_PATH = Path.home() / ".arrow" / "config.toml"


@dataclass
class SearchConfig:
    token_budget: int = 0  # 0 = unlimited (no truncation)
    non_code_penalty: float = 0.3
    frecency_boost: bool = True
    max_results: int = 50


@dataclass
class IndexConfig:
    auto_index_cwd: bool = True
    watch_files: bool = True
    max_file_size_kb: int = 512


@dataclass
class ArrowConfig:
    search: SearchConfig = field(default_factory=SearchConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    db_path: Optional[str] = None
    vector_path: Optional[str] = None

    @staticmethod
    def load(path: Path | str | None = None) -> ArrowConfig:
        """Load config from TOML file.

        Search order (first found wins):
        1. Explicit path argument
        2. ./arrow.toml (project-local)
        3. ~/.arrow/config.toml (global)
        """
        if path:
            path = Path(path)
        else:
            local = Path.cwd() / "arrow.toml"
            path = local if local.is_file() else DEFAULT_CONFIG_PATH
        cfg = ArrowConfig()
        if not path.is_file():
            return cfg

        with open(path, "rb") as f:
            data = tomllib.load(f)

        # [search]
        if "search" in data:
            s = data["search"]
            if "token_budget" in s:
                cfg.search.token_budget = int(s["token_budget"])
            if "non_code_penalty" in s:
                cfg.search.non_code_penalty = float(s["non_code_penalty"])
            if "frecency_boost" in s:
                cfg.search.frecency_boost = bool(s["frecency_boost"])
            if "max_results" in s:
                cfg.search.max_results = int(s["max_results"])

        # [index]
        if "index" in data:
            ix = data["index"]
            if "auto_index_cwd" in ix:
                cfg.index.auto_index_cwd = bool(ix["auto_index_cwd"])
            if "watch_files" in ix:
                cfg.index.watch_files = bool(ix["watch_files"])
            if "max_file_size_kb" in ix:
                cfg.index.max_file_size_kb = int(ix["max_file_size_kb"])

        # top-level paths
        if "db_path" in data:
            cfg.db_path = str(data["db_path"])
        if "vector_path" in data:
            cfg.vector_path = str(data["vector_path"])

        return cfg


# Singleton — loaded once, reused everywhere
_config: ArrowConfig | None = None


def get_config(path: Path | str | None = None) -> ArrowConfig:
    """Get the global config (loaded lazily on first call)."""
    global _config
    if _config is None:
        _config = ArrowConfig.load(path)
    return _config


def reset_config() -> None:
    """Reset cached config (for testing)."""
    global _config
    _config = None
