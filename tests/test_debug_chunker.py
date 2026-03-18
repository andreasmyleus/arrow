"""Diagnostic test to understand tree-sitter behavior."""
from pathlib import Path
from arrow.chunker import _get_parser, _collect_chunks, CHUNK_NODE_TYPES


def test_debug_tree_sitter_ast():
    parser = _get_parser("python")
    code = b"def foo():\n    pass\n\ndef bar():\n    return 1\n"
    tree = parser.parse(code)
    root = tree.root_node

    def show(node, indent=0):
        info = f"{'  ' * indent}{node.type} [{node.start_point} -> {node.end_point}]"
        print(info)
        for child in node.children:
            show(child, indent + 1)

    show(root)

    print("\n--- chunk_types for python ---")
    print(CHUNK_NODE_TYPES.get("python"))

    print("\n--- root children types ---")
    for child in root.children:
        print(f"  child type={child.type}")

    source_lines = code.decode().splitlines()
    chunks = _collect_chunks(root, source_lines, "python", "test.py")
    print(f"\n--- chunks found: {len(chunks)} ---")
    for c in chunks:
        print(f"  name={c.name} kind={c.kind} lines={c.start_line}-{c.end_line}")

    assert len(chunks) >= 2, f"Expected >=2 chunks, got {len(chunks)}: {[c.name for c in chunks]}"
