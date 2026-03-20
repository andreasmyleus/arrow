"""Analysis tools — dependency tracing, impact analysis, diff context, symbol resolution."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .chunker import chunk_file
from .git_utils import _git_cmd, get_diff_hunks
from .server import (
    _NON_CODE_EXTS,
    _PROJECT_NOT_FOUND,
    _fmt_chunks,
    _get_storage,
    _resolve_project_id,
    mcp,
)


@mcp.tool()
def trace_dependencies(
    file: str, depth: int = 2, project: str | None = None
) -> str:
    """Trace import dependencies for a file.

    Args:
        file: Relative path to the file.
        depth: How many levels deep to trace (default 2).
        project: Optional project name to scope the file lookup.

    Returns:
        JSON dependency graph with imports and importers.
    """
    if not file or not file.strip():
        return json.dumps({"error": "file path is required"})
    storage = _get_storage()
    project_id = _resolve_project_id(project)
    file_rec = storage.get_file(file, project_id=project_id)

    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    effective_pid = file_rec.project_id
    if depth < 1:
        return json.dumps({"error": "depth must be >= 1"})
    depth = min(depth, 5)  # Cap at 5

    def _get_imports_for(fid):
        rows = storage.conn.execute(
            "SELECT symbol FROM imports WHERE source_file = ?",
            (fid,),
        ).fetchall()
        return [r[0] for r in rows if r[0]]

    def _get_importers_of(fpath, pid):
        stem = Path(fpath).stem
        if pid is not None:
            rows = storage.conn.execute(
                """SELECT DISTINCT f.path FROM imports i
                   JOIN files f ON f.id = i.source_file
                   WHERE i.symbol LIKE ? AND f.project_id = ?""",
                (f"%{stem}%", pid),
            ).fetchall()
        else:
            rows = storage.conn.execute(
                """SELECT DISTINCT f.path FROM imports i
                   JOIN files f ON f.id = i.source_file
                   WHERE i.symbol LIKE ?""",
                (f"%{stem}%",),
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    # Level-1 results
    imports = _get_imports_for(file_rec.id)
    imported_by = _get_importers_of(file, effective_pid)

    # Recurse for deeper levels
    deeper_importers = {}
    if depth > 1:
        seen = {file}
        frontier = list(set(imported_by))
        for _lvl in range(depth - 1):
            next_frontier = []
            for imp_path in frontier:
                if imp_path in seen:
                    continue
                seen.add(imp_path)
                imp_rec = storage.get_file(imp_path, project_id=effective_pid)
                if imp_rec:
                    trans = _get_importers_of(imp_path, effective_pid)
                    trans = [p for p in trans if p not in seen]
                    if trans:
                        deeper_importers[imp_path] = trans
                        next_frontier.extend(trans)
            frontier = list(set(next_frontier))
            if not frontier:
                break

    result = {
        "file": file,
        "language": file_rec.language,
        "imports": imports,
        "imported_by": imported_by,
        "depth": depth,
    }
    if deeper_importers:
        result["transitive_importers"] = deeper_importers

    return json.dumps(result, indent=2)


@mcp.tool()
def file_summary(path: str, project: str | None = None) -> str:
    """Get a summary of a specific indexed file.

    Args:
        path: Relative path to the file.
        project: Optional project name to scope the file lookup.

    Returns:
        JSON summary with functions, classes, imports, and token counts.
    """
    if not path or not path.strip():
        return json.dumps({"error": "path is required"})

    storage = _get_storage()
    project_id = _resolve_project_id(project)
    file_rec = storage.get_file(path, project_id=project_id)

    if not file_rec:
        return json.dumps({"error": f"File not indexed: {path}"})

    chunks = storage.get_chunks_for_file(file_rec.id)

    functions = []
    classes = []
    other = []
    total_tokens = 0

    for chunk in chunks:
        total_tokens += chunk.token_count or 0
        entry = {
            "name": chunk.name,
            "lines": f"{chunk.start_line}-{chunk.end_line}",
            "tokens": chunk.token_count or 0,
        }
        if chunk.kind in ("function", "method"):
            functions.append(entry)
        elif chunk.kind in ("class", "interface", "enum"):
            classes.append(entry)
        else:
            other.append(entry)

    imports = storage.conn.execute(
        "SELECT symbol FROM imports WHERE source_file = ?",
        (file_rec.id,),
    ).fetchall()

    return json.dumps({
        "path": path,
        "language": file_rec.language,
        "total_tokens": total_tokens,
        "total_chunks": len(chunks),
        "functions": functions,
        "classes": classes,
        "other": other,
        "imports": [row[0] for row in imports if row[0]],
    }, indent=2)


def _git_show_file(root: Path, ref: str, file_path: str) -> str | None:
    """Return file content at a specific git ref, or None on failure."""
    return _git_cmd(root, "show", f"{ref}:{file_path}")


@mcp.tool()
def get_diff_context(
    file: str, line_start: int = 0, line_end: int = 0,
    ref: str | None = None, project: str | None = None,
) -> str:
    """Get changed code plus all callers and dependents of modified functions.

    When reviewing changes, this returns the diff hunks AND the code that
    calls or depends on the changed functions — so you see the full impact
    without reading random files.

    Args:
        file: Relative path to the changed file.
        line_start: Start of line range to focus on (0 = auto-detect from git diff).
        line_end: End of line range (0 = auto-detect from git diff).
        ref: Git ref to diff against (e.g., "HEAD~1", a commit SHA, or branch
             name). When omitted, diffs uncommitted working tree changes against
             HEAD. When provided, diffs against that ref — and if the working
             tree is clean, compares ref~1..ref to show that commit's changes.
        project: Optional project name to scope lookup.

    Returns:
        JSON with changed functions, their callers, dependent files, and code.
    """
    if not file or not file.strip():
        return json.dumps({"error": "file path is required"})
    if line_start < 0 or line_end < 0:
        return json.dumps({"error": "line_start and line_end must be >= 0"})
    if line_start and line_end and line_start > line_end:
        return json.dumps({
            "error": f"line_start ({line_start}) must be <= line_end ({line_end})"
        })
    storage = _get_storage()
    project_id = _resolve_project_id(project)

    file_rec = storage.get_file(file, project_id=project_id)
    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    # Get the project's root path for git operations
    proj = storage.get_project(file_rec.project_id) if file_rec.project_id else None
    root = Path(proj.root_path) if proj and proj.root_path else None

    # Find which functions were changed
    chunks = storage.get_chunks_for_file(file_rec.id)
    changed_functions = []

    if root and root.is_dir():
        effective_ref = ref or "HEAD"
        hunks = get_diff_hunks(root, file, ref=effective_ref)
        if hunks and not line_start:
            # When ref is a historical commit (not HEAD), the diff is
            # ref~1..ref so hunk line numbers correspond to the file at
            # ref, not the current working tree.  Parse chunks from the
            # file at that ref so the overlap check uses matching lines.
            match_chunks = chunks  # default: indexed (working-tree) chunks
            if ref and ref != "HEAD":
                ref_content = _git_show_file(root, ref, file)
                if ref_content is not None:
                    disk_path = root / file
                    ref_chunks = chunk_file(disk_path, ref_content)
                    if ref_chunks:
                        match_chunks = ref_chunks

            # Auto-detect changed line ranges from git diff
            for hunk in hunks:
                hunk_start = hunk["start"]
                hunk_end = hunk_start + hunk["count"]
                for chunk in match_chunks:
                    chunk_name = getattr(chunk, "name", "") or ""
                    chunk_kind = getattr(chunk, "kind", "")
                    chunk_start = getattr(chunk, "start_line", 0)
                    chunk_end = getattr(chunk, "end_line", 0)
                    chunk_content = (
                        getattr(chunk, "content_text", None)
                        or getattr(chunk, "content", None)
                        or ""
                    )
                    if (chunk_start <= hunk_end and
                            chunk_end >= hunk_start and
                            chunk_kind in ("function", "method", "class")):
                        if chunk_name not in [c["name"] for c in changed_functions]:
                            changed_functions.append({
                                "name": chunk_name,
                                "kind": chunk_kind,
                                "lines": f"{chunk_start}-{chunk_end}",
                                "content": chunk_content,
                            })

            # If no indexed chunks matched, re-parse the current file on
            # disk to pick up newly added or shifted functions.
            if not changed_functions:
                disk_path = root / file
                if disk_path.is_file():
                    disk_chunks = chunk_file(
                        disk_path, disk_path.read_text()
                    )
                    for hunk in hunks:
                        hunk_start = hunk["start"]
                        hunk_end = hunk_start + hunk["count"]
                        for dc in disk_chunks:
                            if (dc.start_line <= hunk_end
                                    and dc.end_line >= hunk_start
                                    and dc.kind in (
                                        "function", "method", "class",
                                    )):
                                name = dc.name or ""
                                if name not in [
                                    c["name"] for c in changed_functions
                                ]:
                                    changed_functions.append({
                                        "name": name,
                                        "kind": dc.kind,
                                        "lines": (
                                            f"{dc.start_line}-{dc.end_line}"
                                        ),
                                        "content": dc.content or "",
                                    })

    if line_start and line_end:
        for chunk in chunks:
            if (chunk.start_line <= line_end and
                    chunk.end_line >= line_start and
                    chunk.kind in ("function", "method", "class")):
                if chunk.name not in [c["name"] for c in changed_functions]:
                    changed_functions.append({
                        "name": chunk.name,
                        "kind": chunk.kind,
                        "lines": f"{chunk.start_line}-{chunk.end_line}",
                        "content": chunk.content_text or "",
                    })

    # Find callers/dependents for each changed function
    callers = []
    seen_callers = set()
    for func in changed_functions:
        func_callers = storage.get_callers_of_symbol(
            func["name"], project_id=file_rec.project_id
        )
        for caller in func_callers:
            # Skip non-code files (docs, data files)
            ext = Path(caller["file_path"]).suffix.lower()
            if ext in _NON_CODE_EXTS:
                continue
            caller_key = (caller["file_path"], caller["name"])
            if caller_key not in seen_callers:
                seen_callers.add(caller_key)
                callers.append({
                    "file": caller["file_path"],
                    "name": caller["name"],
                    "kind": caller["kind"],
                    "lines": f"{caller['start_line']}-{caller['end_line']}",
                    "calls": func["name"],
                })

    # Find files that import this file
    importers = storage.get_importers_of_file(
        file, project_id=file_rec.project_id
    )

    parts = [f"# {file} — diff context"]
    if changed_functions:
        parts.append(f"\n## Changed functions ({len(changed_functions)})")
        parts.append(_fmt_chunks(changed_functions))
    if callers:
        parts.append(f"\n## Callers ({len(callers)} total, showing {min(len(callers), 30)})")
        for caller in callers[:30]:
            parts.append(
                f"- {caller['file']}:{caller['lines']}  {caller['kind']}"
                f" {caller['name']}  (calls {caller['calls']})"
            )
    if importers:
        parts.append(f"\n## Dependent files ({len(importers)})")
        for imp in importers:
            parts.append(f"- {imp['path']}  ({imp.get('language', '?')})")
    return "\n".join(parts)


@mcp.tool()
def what_breaks_if_i_change(
    file: str, function: str | None = None, project: str | None = None
) -> str:
    """Trace reverse dependencies to show what breaks if you change a file or function.

    Returns all callers, test files that exercise the function, config files
    that reference it, and dependent files across the full index.

    Args:
        file: Relative path to the file you plan to change.
        function: Optional specific function name. If omitted, analyzes all
                  exported symbols in the file.
        project: Optional project name to scope lookup.

    Returns:
        JSON impact report with callers, tests, dependents, and risk assessment.
    """
    if not file or not file.strip():
        return json.dumps({"error": "file path is required"})
    storage = _get_storage()
    project_id = _resolve_project_id(project)

    file_rec = storage.get_file(file, project_id=project_id)
    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    effective_pid = file_rec.project_id

    # Get symbols to analyze
    if function:
        target_symbols = [function]
    else:
        chunks = storage.get_chunks_for_file(file_rec.id)
        target_symbols = [
            c.name for c in chunks
            if c.kind in ("function", "method", "class")
            and c.name and c.name != "<anonymous>"
            # Skip dunder methods — __init__, __str__, etc. generate
            # massive noise since every class has them
            and not (c.name.startswith("__") and c.name.endswith("__"))
        ]

    # Find all callers for each symbol
    all_callers = []
    seen = set()
    for sym in target_symbols:
        callers = storage.get_callers_of_symbol(sym, project_id=effective_pid)
        for caller in callers:
            # Skip non-code files (docs, data) — they reference the symbol
            # textually but won't break from a code change
            ext = Path(caller["file_path"]).suffix.lower()
            if ext in _NON_CODE_EXTS:
                continue
            key = (caller["file_path"], caller["name"])
            if key not in seen:
                seen.add(key)
                all_callers.append({
                    "file": caller["file_path"],
                    "name": caller["name"],
                    "kind": caller["kind"],
                    "calls": sym,
                })

    # Find test files that reference any of the target symbols
    test_files = storage.get_test_files(project_id=effective_pid)
    test_file_ids = [tf.id for tf in test_files]

    affected_tests = []
    seen_tests = set()
    for sym in target_symbols:
        test_refs = storage.find_chunks_referencing(sym, test_file_ids)
        for ref in test_refs:
            test_key = (ref["file_path"], ref["name"])
            if test_key not in seen_tests:
                seen_tests.add(test_key)
                affected_tests.append({
                    "file": ref["file_path"],
                    "test_name": ref["name"],
                    "references": sym,
                })

    # Find files that import this module
    importers = storage.get_importers_of_file(file, project_id=effective_pid)

    # Risk assessment
    caller_count = len(all_callers)
    test_count = len(affected_tests)
    importer_count = len(importers)

    if caller_count > 20 or importer_count > 10:
        risk = "high"
    elif caller_count > 5 or importer_count > 3:
        risk = "medium"
    else:
        risk = "low"

    return json.dumps({
        "file": file,
        "symbols_analyzed": target_symbols,
        "risk": risk,
        "callers": all_callers[:50],
        "affected_tests": affected_tests[:30],
        "dependent_files": [
            {"path": imp["path"]} for imp in importers
        ],
        "summary": {
            "total_callers": caller_count,
            "total_tests": test_count,
            "total_dependents": importer_count,
        },
    }, indent=2)


@mcp.tool()
def resolve_symbol(
    symbol: str, project: str | None = None
) -> str:
    """Resolve a symbol across all indexed repos (cross-repo import resolution).

    When you see `from shared_lib import auth`, this tool finds which indexed
    repo contains `shared_lib.auth` and returns its definition. Works across
    all indexed projects.

    Args:
        symbol: The symbol name to resolve (e.g. "auth", "DatabaseClient").
        project: Optional source project name — results from other projects
                 are prioritized.

    Returns:
        JSON with all matching definitions across repos, with code.
    """
    storage = _get_storage()

    if not symbol or not symbol.strip():
        return json.dumps({"error": "symbol is required"})

    source_pid = _resolve_project_id(project)
    # If project was given but not found, treat as no-project filter
    if source_pid == _PROJECT_NOT_FOUND:
        source_pid = None

    # Search across all repos (exact match first)
    results = storage.resolve_symbol_across_repos(
        symbol, exclude_project_id=source_pid
    )

    # Also search within source project for completeness
    local_results = storage.resolve_symbol_across_repos(symbol)

    # Fallback to prefix match if exact match found nothing
    if not results and not local_results:
        prefix_results = storage.search_symbols(symbol, limit=20)
        for sym_rec in prefix_results:
            file_rec = storage.get_file_by_id(sym_rec.file_id)
            if not file_rec:
                continue
            proj = storage.get_project(
                file_rec.project_id
            ) if file_rec.project_id else None
            chunk = storage.get_chunk_by_id(
                sym_rec.chunk_id
            ) if sym_rec.chunk_id else None
            local_results.append({
                "name": sym_rec.name,
                "kind": sym_rec.kind,
                "path": file_rec.path,
                "project_id": file_rec.project_id,
                "project_name": proj.name if proj else "",
                "start_line": chunk.start_line if chunk else 0,
                "end_line": chunk.end_line if chunk else 0,
                "content_text": chunk.content_text if chunk else "",
            })

    # Deduplicate: cross-repo first, then local
    seen = set()
    output = []
    for result in results + local_results:
        key = (result["project_name"], result["path"], result["name"])
        if key not in seen:
            seen.add(key)
            content = result.get("content_text", "") or ""
            truncated = len(content) > 2000
            if truncated:
                content = content[:2000] + "\n... (truncated)"
            output.append({
                "symbol": result["name"],
                "kind": result["kind"],
                "file": result["path"],
                "project": result["project_name"],
                "lines": f"{result['start_line']}-{result['end_line']}",
                "content": content,
                "truncated": truncated,
                "cross_repo": result["project_id"] != source_pid if source_pid else False,
            })

    if not output:
        return f"No definitions found for '{symbol}'"
    parts = [f"resolve: {symbol}  ({len(output)} result{'s' if len(output) != 1 else ''})"]
    for item in output[:20]:
        tag = " [cross-repo]" if item.get("cross_repo") else ""
        header = f"\n# {item['file']}:{item['lines']}  {item['kind']} {item['symbol']}{tag}"
        if item.get("project"):
            header += f"  ({item['project']})"
        parts.append(header)
        content = item.get("content", "")
        if content:
            if item.get("truncated"):
                parts.append(content + "\n... (truncated)")
            else:
                parts.append(content)
    return "\n".join(parts)


@mcp.tool()
def get_tests_for(
    function: str, file: str | None = None, project: str | None = None
) -> str:
    """Find test code for a specific function via import tracing + naming conventions.

    Maps a function to its test files by:
    1. Finding test files that import the source module
    2. Finding test functions whose names match (test_<function>)
    3. Finding test chunks that reference the function name

    Args:
        function: The function name to find tests for.
        file: Optional source file path (narrows the search).
        project: Optional project name.

    Returns:
        JSON with matching test functions and their code.
    """
    if not function or not function.strip():
        return json.dumps({"error": "function name is required"})

    storage = _get_storage()
    project_id = _resolve_project_id(project)

    # Get all test files, filtering out non-code files (benchmarks, docs, etc.)
    _test_file_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go",
                       ".rs", ".java", ".kt", ".cs", ".cpp", ".c"}
    raw_test_files = storage.get_test_files(project_id=project_id)
    test_files = [
        tf for tf in raw_test_files
        if Path(tf.path).suffix.lower() in _test_file_exts
        and "/benchmark" not in tf.path.lower()
        and "/bench_" not in tf.path.lower()
    ]
    if not test_files:
        return json.dumps({
            "function": function,
            "tests": [],
            "message": "No test files found in the index.",
        })

    # Strategy 1: Find test functions named test_<function> or test<Function>
    camel_name = function[0].upper() + function[1:] if function else ""
    matching_tests = []
    seen = set()

    name_patterns = [
        f"test_{function}",
        f"Test{camel_name}",
        f"test{camel_name}",
    ]

    # Pre-compile regex for content/filename matching
    func_re = re.compile(rf'\b{re.escape(function)}\b')

    # Identify test files whose filename contains the function name
    # (e.g., test_search_regex.py matches function "search")
    filename_match_ids = set()
    for tf in test_files:
        tf_stem = Path(tf.path).stem
        if func_re.search(tf_stem):
            filename_match_ids.add(tf.id)

    # Find test files that import the source module
    import_match_ids = set()
    if file:
        source_stems = {Path(file).stem}
    else:
        # Resolve which files define this function from the index
        source_stems = set()
        func_syms = storage.search_symbols(function, limit=10)
        for sym in func_syms:
            if sym.name == function:
                frec = storage.get_file_by_id(sym.file_id)
                if frec and (project_id is None or frec.project_id == project_id):
                    source_stems.add(Path(frec.path).stem)

    if source_stems:
        for tf in test_files:
            imports = storage.conn.execute(
                "SELECT symbol FROM imports WHERE source_file = ?",
                (tf.id,),
            ).fetchall()
            if any(
                s in (imp[0] or "")
                for imp in imports
                for s in source_stems
            ):
                import_match_ids.add(tf.id)

    # conftest files only contribute via import tracing, not content search
    conftest_ids = {tf.id for tf in test_files
                    if Path(tf.path).name == "conftest.py"}

    for tf in test_files:
        chunks = storage.get_chunks_for_file(tf.id)
        is_conftest = tf.id in conftest_ids
        file_is_relevant = (
            tf.id in filename_match_ids or tf.id in import_match_ids
        )
        for chunk in chunks:
            # Skip fixtures, helpers, and non-test functions in test files
            # Only allow test functions (test_*) or classes (Test*) through
            # content/reference matching
            is_test_chunk = (
                chunk.name
                and (chunk.name.startswith("test_")
                     or chunk.name.startswith("Test"))
            )

            # Match by naming convention
            name_match = any(
                chunk.name and chunk.name.startswith(pat)
                for pat in name_patterns
            )
            # Match by content reference (word-boundary to avoid
            # false positives for short names like "get", "set")
            content_match = False
            if chunk.content_text and not name_match:
                content_match = bool(func_re.search(chunk.content_text))
            # For filename/import-matched files, include chunks that
            # reference the function even if name didn't match
            file_match = False
            if file_is_relevant and not name_match and not content_match:
                if chunk.content_text and func_re.search(chunk.content_text):
                    file_match = True

            # For content/reference/file matches, only include actual test
            # functions — skip fixtures, helpers, conftest utilities
            if name_match:
                pass  # name matches are always relevant
            elif (content_match or file_match) and (
                not is_test_chunk or is_conftest
            ):
                continue  # skip non-test chunks and conftest helpers

            if name_match or content_match or file_match:
                key = (tf.path, chunk.name)
                if key not in seen:
                    seen.add(key)
                    if name_match:
                        match_type = "name"
                    elif content_match:
                        match_type = "reference"
                    elif tf.id in import_match_ids:
                        match_type = "import"
                    else:
                        match_type = "filename"
                    matching_tests.append({
                        "file": tf.path,
                        "test_name": chunk.name,
                        "kind": chunk.kind,
                        "lines": f"{chunk.start_line}-{chunk.end_line}",
                        "content": chunk.content_text or "",
                        "match_type": match_type,
                    })

    # Sort by relevance: name matches first, then reference, then import/filename
    _match_priority = {"name": 0, "reference": 1, "import": 2, "filename": 3}
    matching_tests.sort(key=lambda t: _match_priority.get(t["match_type"], 9))

    # Cap results to keep output focused
    max_results = 20
    all_tests = matching_tests[:max_results]

    if not all_tests:
        msg = f"No tests found for '{function}'"
        if file:
            msg += f" in {file}"
        return msg
    total = len(matching_tests)
    shown = min(total, max_results)
    header = f"tests for: {function}  ({shown} found"
    if total > max_results:
        header += f", showing {shown}/{total}"
    header += ")"
    if file:
        header += f"  source: {file}"
    return header + "\n\n" + _fmt_chunks(all_tests)
