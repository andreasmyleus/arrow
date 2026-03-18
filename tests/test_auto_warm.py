"""Tests for auto-warm on session start."""

import os
import subprocess
import tempfile


class TestAutoWarm:
    def test_auto_warm_skips_non_git(self, tmp_path):
        """Auto-warm should skip non-git directories."""
        db_path = tempfile.mktemp(suffix=".db")
        vec_path = tempfile.mktemp(suffix=".usearch")
        os.environ["ARROW_DB_PATH"] = db_path
        os.environ["ARROW_VECTOR_PATH"] = vec_path

        try:
            original_cwd = os.getcwd()
            os.chdir(tmp_path)

            from arrow.server import _auto_warm_cwd
            # Should not crash on non-git directory
            _auto_warm_cwd()

            os.chdir(original_cwd)
        finally:
            os.environ.pop("ARROW_DB_PATH", None)
            os.environ.pop("ARROW_VECTOR_PATH", None)
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_auto_warm_indexes_git_dir(self, tmp_path):
        """Auto-warm should index a git directory."""
        db_path = tempfile.mktemp(suffix=".db")
        vec_path = tempfile.mktemp(suffix=".usearch")
        os.environ["ARROW_DB_PATH"] = db_path
        os.environ["ARROW_VECTOR_PATH"] = vec_path

        # Create a git repo
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        (tmp_path / "hello.py").write_text("def hello(): pass\n")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )

        try:
            original_cwd = os.getcwd()
            os.chdir(tmp_path)

            from arrow.server import _auto_warm_cwd
            _auto_warm_cwd()

            # Give background thread a moment
            import time
            time.sleep(2)

            # Check that something was indexed
            import arrow.server as srv
            storage = srv._get_storage()
            projects = storage.list_projects()
            assert len(projects) >= 1

            os.chdir(original_cwd)
        finally:
            os.environ.pop("ARROW_DB_PATH", None)
            os.environ.pop("ARROW_VECTOR_PATH", None)
            if os.path.exists(db_path):
                os.unlink(db_path)
