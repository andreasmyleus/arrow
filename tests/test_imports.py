"""Tests for multi-language import resolution."""


class TestMultiLangImports:
    def test_python_imports_indexed(self, setup_server):
        """Python imports should be resolved during indexing."""
        import arrow.server as srv
        storage = srv._get_storage()
        projects = storage.list_projects()
        pid = projects[0].id
        files = storage.get_all_files(project_id=pid)
        # api.py imports from auth — check import relationships
        api_file = next(
            (f for f in files if "api" in f.path), None
        )
        auth_file = next(
            (f for f in files if "auth" in f.path), None
        )
        if api_file and auth_file:
            importers = storage.get_importers_of_file(
                auth_file.path
            )
            paths = [i["path"] for i in importers]
            assert any("api" in p for p in paths)

    def test_multi_lang_import_parser(self):
        """Test import extraction for various languages."""
        from arrow.indexer import _extract_imports
        # Test JS/TS import
        js_lines = ['import { foo } from "./bar";']
        imps = _extract_imports(js_lines, "javascript")
        assert len(imps) > 0

    def test_go_import_parser(self):
        from arrow.indexer import _extract_imports
        go_lines = [
            'import (',
            '    "fmt"',
            '    "net/http"',
            ')',
        ]
        imps = _extract_imports(go_lines, "go")
        assert len(imps) > 0

    def test_rust_use_parser(self):
        from arrow.indexer import _extract_imports
        rust_lines = ['use std::collections::HashMap;']
        imps = _extract_imports(rust_lines, "rust")
        assert len(imps) > 0
