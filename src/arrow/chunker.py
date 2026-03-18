"""tree-sitter AST chunking with fallback for unknown file types."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import zstandard as zstd

logger = logging.getLogger(__name__)

# Cache for loaded tree-sitter parsers per language
_languages: dict[str, object] = {}

# Map file extensions to tree-sitter language names
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "bash",
    ".hs": "haskell",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".clj": "clojure",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".jl": "julia",
    ".dart": "dart",
    ".zig": "zig",
    ".nim": "nim",
    ".v": "v",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".xml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".tex": "latex",
    ".elm": "elm",
    ".vue": "vue",
    ".svelte": "svelte",
    ".tf": "hcl",
    ".hcl": "hcl",
    ".proto": "proto",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".cmake": "cmake",
    ".dockerfile": "dockerfile",
    ".m": "objc",
    ".mm": "objc",
}

# tree-sitter node types that represent meaningful code chunks
CHUNK_NODE_TYPES: dict[str, set[str]] = {
    "python": {
        "function_definition",
        "class_definition",
        "decorated_definition",
    },
    "javascript": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
    },
    "typescript": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
        "interface_declaration",
        "type_alias_declaration",
    },
    "tsx": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "export_statement",
        "interface_declaration",
        "type_alias_declaration",
    },
    "rust": {
        "function_item",
        "impl_item",
        "struct_item",
        "enum_item",
        "trait_item",
        "mod_item",
    },
    "go": {
        "function_declaration",
        "method_declaration",
        "type_declaration",
    },
    "java": {
        "class_declaration",
        "method_declaration",
        "interface_declaration",
        "enum_declaration",
        "constructor_declaration",
    },
    "c": {
        "function_definition",
        "struct_specifier",
        "enum_specifier",
    },
    "cpp": {
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "namespace_definition",
    },
    "ruby": {
        "method",
        "class",
        "module",
        "singleton_method",
    },
    "c_sharp": {
        "class_declaration",
        "method_declaration",
        "interface_declaration",
        "struct_declaration",
        "enum_declaration",
    },
    "php": {
        "function_definition",
        "class_declaration",
        "method_declaration",
    },
    "swift": {
        "function_declaration",
        "class_declaration",
        "struct_declaration",
        "enum_declaration",
        "protocol_declaration",
    },
    "kotlin": {
        "function_declaration",
        "class_declaration",
        "object_declaration",
    },
}

# Default node types for languages not explicitly listed
DEFAULT_CHUNK_TYPES = {
    "function_definition",
    "function_declaration",
    "class_definition",
    "class_declaration",
    "method_definition",
    "method_declaration",
    "impl_item",
    "struct_item",
    "enum_item",
    "trait_item",
    "interface_declaration",
    "type_declaration",
    "module",
}

# Zstandard compressor/decompressor (reuse for efficiency)
_zstd_compressor = zstd.ZstdCompressor(level=3)
_zstd_decompressor = zstd.ZstdDecompressor()


@dataclass
class Chunk:
    """A semantic code chunk extracted from a file."""

    name: str
    kind: str  # function, class, method, module
    start_line: int
    end_line: int
    content: str  # raw source text
    scope_context: str  # e.g. "src/api/auth.py::AuthHandler.login"


def compress_content(text: str) -> bytes:
    """Compress chunk content with zstd."""
    return _zstd_compressor.compress(text.encode("utf-8"))


def decompress_content(data: bytes) -> str:
    """Decompress chunk content from zstd."""
    return _zstd_decompressor.decompress(data).decode("utf-8")


def detect_language(filepath: Path) -> Optional[str]:
    """Detect language from file extension."""
    # Handle Dockerfile specially
    if filepath.name.lower().startswith("dockerfile"):
        return "dockerfile"
    return EXTENSION_MAP.get(filepath.suffix.lower())


def _get_parser(language: str):
    """Get or create a tree-sitter parser for the given language."""
    import tree_sitter_languages

    if language not in _languages:
        try:
            parser = tree_sitter_languages.get_parser(language)
            _languages[language] = parser
        except Exception:
            logger.debug("No tree-sitter grammar for: %s", language)
            return None

    return _languages[language]


def _get_node_children(node) -> list:
    """Get children of a node, handling different tree-sitter API versions."""
    # Try node.children first (works in most versions)
    try:
        children = node.children
        if children is not None and len(children) > 0:
            return list(children)
    except (AttributeError, TypeError):
        pass

    # Fall back to TreeCursor-based traversal
    try:
        cursor = node.walk()
        if not cursor.goto_first_child():
            return []
        children = []
        while True:
            children.append(cursor.node)
            if not cursor.goto_next_sibling():
                break
        return children
    except (AttributeError, TypeError):
        pass

    # Last resort: try child_count + child()
    try:
        count = node.child_count
        return [node.child(i) for i in range(count)]
    except (AttributeError, TypeError):
        return []


def _extract_name(node, source_lines: list[str]) -> str:
    """Extract the name of a node (function/class name)."""
    # Look for name/identifier child nodes
    children = _get_node_children(node)
    for child in children:
        if child.type in ("identifier", "name", "type_identifier", "property_identifier"):
            return source_lines[child.start_point[0]][
                child.start_point[1] : child.end_point[1]
            ]
    # For decorated definitions, look deeper
    for child in children:
        if child.type in CHUNK_NODE_TYPES.get("python", set()) | DEFAULT_CHUNK_TYPES:
            return _extract_name(child, source_lines)
    return "<anonymous>"


def _node_kind(node_type: str) -> str:
    """Map tree-sitter node type to a normalized kind."""
    if "class" in node_type or "struct" in node_type:
        return "class"
    if "method" in node_type:
        return "method"
    if "function" in node_type or "arrow_function" in node_type:
        return "function"
    if "interface" in node_type or "trait" in node_type or "protocol" in node_type:
        return "interface"
    if "enum" in node_type:
        return "enum"
    if "impl" in node_type:
        return "impl"
    if "module" in node_type or "namespace" in node_type or "mod" in node_type:
        return "module"
    if "type" in node_type:
        return "type"
    if "export" in node_type:
        return "export"
    return "other"


def _collect_chunks(
    node,
    source_lines: list[str],
    language: str,
    filepath: str,
    parent_name: Optional[str] = None,
) -> list[Chunk]:
    """Recursively collect semantic chunks from the AST."""
    chunks = []
    chunk_types = CHUNK_NODE_TYPES.get(language, DEFAULT_CHUNK_TYPES)

    if node.type in chunk_types:
        name = _extract_name(node, source_lines)
        kind = _node_kind(node.type)
        start_line = node.start_point[0] + 1  # 1-indexed
        end_line = node.end_point[0] + 1
        content = "\n".join(source_lines[node.start_point[0] : node.end_point[0] + 1])

        scope = filepath
        if parent_name:
            scope = f"{filepath}::{parent_name}.{name}"
        else:
            scope = f"{filepath}::{name}"

        chunks.append(
            Chunk(
                name=name,
                kind=kind,
                start_line=start_line,
                end_line=end_line,
                content=content,
                scope_context=scope,
            )
        )

        # Recurse into children for nested definitions (e.g., methods in a class)
        # But skip if this is a decorated_definition — the inner function/class
        # is already captured in this chunk's content, so recursing would create
        # a near-duplicate.
        if node.type != "decorated_definition":
            current_name = f"{parent_name}.{name}" if parent_name else name
            for child in _get_node_children(node):
                chunks.extend(
                    _collect_chunks(child, source_lines, language, filepath, current_name)
                )
    else:
        # Not a chunk node — recurse into children
        for child in _get_node_children(node):
            chunks.extend(
                _collect_chunks(child, source_lines, language, filepath, parent_name)
            )

    return chunks


def _collect_chunks_cursor(
    tree,
    source_lines: list[str],
    language: str,
    filepath: str,
) -> list[Chunk]:
    """Collect semantic chunks using TreeCursor walk (fallback method).

    Uses a non-recursive cursor-based walk which is more reliable across
    different tree-sitter versions.
    """
    chunks = []
    chunk_types = CHUNK_NODE_TYPES.get(language, DEFAULT_CHUNK_TYPES)

    cursor = tree.walk()

    # Build a parent name stack for scope tracking
    # We walk the tree depth-first using the cursor
    visited = set()
    parent_stack: list[str] = []
    depth_stack: list[int] = []

    def _process_node(node, parent_name: Optional[str] = None):
        if node.type in chunk_types:
            name = _extract_name(node, source_lines)
            kind = _node_kind(node.type)
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            content_text = "\n".join(
                source_lines[node.start_point[0] : node.end_point[0] + 1]
            )

            if parent_name:
                scope = f"{filepath}::{parent_name}.{name}"
            else:
                scope = f"{filepath}::{name}"

            chunks.append(
                Chunk(
                    name=name,
                    kind=kind,
                    start_line=start_line,
                    end_line=end_line,
                    content=content_text,
                    scope_context=scope,
                )
            )
            return name
        return None

    # Depth-first traversal using cursor
    current_depth = 0
    reached = True

    while reached:
        node = cursor.node
        node_id = id(node)

        if node_id not in visited:
            visited.add(node_id)

            # Trim parent stack to current depth
            while depth_stack and depth_stack[-1] >= current_depth:
                depth_stack.pop()
                parent_stack.pop()

            parent_name = parent_stack[-1] if parent_stack else None
            chunk_name = _process_node(node, parent_name)

            if chunk_name:
                parent_stack.append(
                    f"{parent_name}.{chunk_name}" if parent_name else chunk_name
                )
                depth_stack.append(current_depth)

                # Skip children of decorated_definition to avoid
                # creating a near-duplicate chunk for the inner def/class
                if node.type == "decorated_definition":
                    if cursor.goto_next_sibling():
                        continue
                    retracing = True
                    while retracing:
                        if not cursor.goto_parent():
                            retracing = False
                            reached = False
                        else:
                            current_depth -= 1
                            if cursor.goto_next_sibling():
                                retracing = False
                    continue

        if cursor.goto_first_child():
            current_depth += 1
            continue
        if cursor.goto_next_sibling():
            continue
        # Go back up
        retracing = True
        while retracing:
            if not cursor.goto_parent():
                retracing = False
                reached = False
            else:
                current_depth -= 1
                if cursor.goto_next_sibling():
                    retracing = False

    return chunks


def chunk_file_treesitter(filepath: Path, content: str, language: str) -> list[Chunk]:
    """Chunk a file using tree-sitter AST parsing."""
    parser = _get_parser(language)
    if parser is None:
        return []

    try:
        tree = parser.parse(content.encode("utf-8"))
    except Exception:
        logger.warning("tree-sitter parse error for %s", filepath)
        return []

    source_lines = content.splitlines()
    rel_path = str(filepath)

    # Try the recursive node.children approach first
    chunks = _collect_chunks(tree.root_node, source_lines, language, rel_path)

    # If that didn't find anything, try cursor-based traversal
    # (more robust across tree-sitter API versions)
    if not chunks and content.strip():
        chunks = _collect_chunks_cursor(tree, source_lines, language, rel_path)

    # If still no semantic chunks found, fall back to module-level chunk
    if not chunks and content.strip():
        chunks = [
            Chunk(
                name=filepath.name,
                kind="module",
                start_line=1,
                end_line=len(source_lines),
                content=content,
                scope_context=rel_path,
            )
        ]

    return chunks


# -- Regex-based fallback for when tree-sitter is unavailable --

# Patterns for extracting definitions from source code via regex
_REGEX_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [
        (r"^(class)\s+(\w+)", "class"),
        (r"^(def)\s+(\w+)", "function"),
        (r"^(@\w[\w.]*\s*(?:\(.*?\)\s*)*\n(?:@\w[\w.]*\s*(?:\(.*?\)\s*)*\n)*)?(def)\s+(\w+)", "function"),
    ],
    "javascript": [
        (r"^(?:export\s+)?function\s+(\w+)", "function"),
        (r"^(?:export\s+)?class\s+(\w+)", "class"),
        (r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=])\s*=>", "function"),
    ],
    "typescript": [
        (r"^(?:export\s+)?function\s+(\w+)", "function"),
        (r"^(?:export\s+)?class\s+(\w+)", "class"),
        (r"^(?:export\s+)?interface\s+(\w+)", "interface"),
        (r"^(?:export\s+)?type\s+(\w+)", "type"),
        (r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=])\s*=>", "function"),
    ],
    "rust": [
        (r"^(?:pub\s+)?fn\s+(\w+)", "function"),
        (r"^(?:pub\s+)?struct\s+(\w+)", "class"),
        (r"^(?:pub\s+)?enum\s+(\w+)", "enum"),
        (r"^(?:pub\s+)?trait\s+(\w+)", "interface"),
        (r"^impl(?:<[^>]*>)?\s+(\w+)", "impl"),
    ],
    "go": [
        (r"^func\s+(\w+)", "function"),
        (r"^func\s+\([^)]+\)\s+(\w+)", "function"),
        (r"^type\s+(\w+)\s+struct", "class"),
        (r"^type\s+(\w+)\s+interface", "interface"),
        (r"^type\s+(\w+)", "type"),
    ],
    "java": [
        (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?class\s+(\w+)", "class"),
        (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?interface\s+(\w+)", "interface"),
        (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(", "function"),
    ],
}


def _chunk_file_regex(filepath: Path, content: str, language: str) -> list[Chunk]:
    """Extract chunks using regex patterns when tree-sitter is unavailable."""
    patterns = _REGEX_PATTERNS.get(language)
    if not patterns:
        return []

    lines = content.splitlines()
    if not lines:
        return []

    rel_path = str(filepath)

    # Find all definition start lines
    definitions: list[tuple[int, str, str]] = []  # (line_idx, name, kind)
    for line_idx, line in enumerate(lines):
        stripped = line.lstrip()
        for pattern, kind in patterns:
            m = re.match(pattern, stripped)
            if m:
                # The name is the last group in the match
                name = m.group(m.lastindex)
                definitions.append((line_idx, name, kind))
                break  # Only match one pattern per line

    if not definitions:
        return []

    # Determine the end of each definition: next definition at same or lower
    # indent, or end of file
    chunks = []
    for i, (start_idx, name, kind) in enumerate(definitions):
        # Find end of this definition
        if i + 1 < len(definitions):
            # Look for the end: either next definition start or a blank line
            # before the next definition
            next_start = definitions[i + 1][0]
            end_idx = next_start
            # Walk backwards from next definition to find blank line separator
            for j in range(next_start - 1, start_idx, -1):
                if not lines[j].strip():
                    end_idx = j
                    break
        else:
            end_idx = len(lines)

        # Trim trailing blank lines
        while end_idx > start_idx + 1 and not lines[end_idx - 1].strip():
            end_idx -= 1

        chunk_content = "\n".join(lines[start_idx:end_idx])
        scope = f"{rel_path}::{name}"

        chunks.append(
            Chunk(
                name=name,
                kind=kind,
                start_line=start_idx + 1,
                end_line=end_idx,
                content=chunk_content,
                scope_context=scope,
            )
        )

    return chunks


# -- Fallback chunking for unknown file types --

FALLBACK_CHUNK_SIZE = 100  # lines per chunk
FALLBACK_OVERLAP = 10  # overlap lines


def chunk_file_fallback(filepath: Path, content: str) -> list[Chunk]:
    """Line-based chunking for files without tree-sitter support.

    Splits into ~100-line chunks with 10-line overlap, trying to break
    at blank lines for cleaner boundaries.
    """
    lines = content.splitlines()
    if not lines:
        return []

    # Small files: single chunk
    if len(lines) <= FALLBACK_CHUNK_SIZE + FALLBACK_OVERLAP:
        return [
            Chunk(
                name=filepath.name,
                kind="module",
                start_line=1,
                end_line=len(lines),
                content=content,
                scope_context=str(filepath),
            )
        ]

    chunks = []
    i = 0
    chunk_idx = 0
    while i < len(lines):
        end = min(i + FALLBACK_CHUNK_SIZE, len(lines))

        # Try to find a blank line near the boundary for a cleaner split
        if end < len(lines):
            for j in range(end, max(end - 20, i), -1):
                if not lines[j].strip():
                    end = j + 1
                    break

        chunk_content = "\n".join(lines[i:end])
        chunks.append(
            Chunk(
                name=f"{filepath.name}:chunk_{chunk_idx}",
                kind="module",
                start_line=i + 1,
                end_line=end,
                content=chunk_content,
                scope_context=f"{filepath}::chunk_{chunk_idx}",
            )
        )

        chunk_idx += 1
        i = end - FALLBACK_OVERLAP if end < len(lines) else end

    return chunks


def chunk_file(filepath: Path, content: str) -> list[Chunk]:
    """Chunk a file using tree-sitter if available, fallback otherwise."""
    language = detect_language(filepath)

    if language:
        chunks = chunk_file_treesitter(filepath, content, language)
        if chunks:
            # If tree-sitter only returned a single module-level chunk,
            # try regex-based extraction for better granularity
            if len(chunks) == 1 and chunks[0].kind == "module":
                regex_chunks = _chunk_file_regex(filepath, content, language)
                if regex_chunks:
                    return regex_chunks
            return chunks

        # Tree-sitter returned nothing; try regex-based chunking
        regex_chunks = _chunk_file_regex(filepath, content, language)
        if regex_chunks:
            return regex_chunks

    # Fallback for unsupported or failed parsing
    return chunk_file_fallback(filepath, content)
