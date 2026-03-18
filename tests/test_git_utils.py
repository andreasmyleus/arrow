"""Tests for git utilities."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from arrow.git_utils import (
    get_changed_files_between, get_commit_info, get_file_at_commit,
    get_git_info, get_merge_base, has_new_commits, is_git_repo,
    list_files_at_commit, parse_remote_url, resolve_commit,
)


class TestParseRemoteUrl:
    def test_https_github(self):
        org, repo = parse_remote_url("https://github.com/anthropics/claude-code.git")
        assert org == "anthropics"
        assert repo == "claude-code"

    def test_https_no_git_suffix(self):
        org, repo = parse_remote_url("https://github.com/org/repo")
        assert org == "org"
        assert repo == "repo"

    def test_ssh_github(self):
        org, repo = parse_remote_url("git@github.com:anthropics/claude-code.git")
        assert org == "anthropics"
        assert repo == "claude-code"

    def test_ssh_no_git_suffix(self):
        org, repo = parse_remote_url("git@github.com:org/repo")
        assert org == "org"
        assert repo == "repo"

    def test_ssh_protocol_url(self):
        org, repo = parse_remote_url("ssh://git@github.com/org/repo.git")
        assert org == "org"
        assert repo == "repo"

    def test_gitlab(self):
        org, repo = parse_remote_url("https://gitlab.com/mygroup/myproject.git")
        assert org == "mygroup"
        assert repo == "myproject"


class TestIsGitRepo:
    def test_real_repo(self, tmp_path):
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        assert is_git_repo(tmp_path)

    def test_not_a_repo(self, tmp_path):
        assert not is_git_repo(tmp_path)


class TestGetGitInfo:
    def test_git_repo_with_remote(self, tmp_path):
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "remote", "add", "origin",
             "https://github.com/testorg/testrepo.git"],
            capture_output=True,
        )
        # Need at least one commit for HEAD
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."], capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )

        info = get_git_info(tmp_path)
        assert info["name"] == "testorg/testrepo"
        assert info["branch"] is not None
        assert info["commit"] is not None
        assert len(info["commit"]) == 40
        assert info["remote_url"] == "https://github.com/testorg/testrepo.git"

    def test_git_repo_no_remote(self, tmp_path):
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."], capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )

        info = get_git_info(tmp_path)
        assert info["name"] == tmp_path.name  # Falls back to dir name
        assert info["branch"] is not None
        assert info["remote_url"] is None

    def test_not_a_repo(self, tmp_path):
        info = get_git_info(tmp_path)
        assert info["name"] == tmp_path.name
        assert info["branch"] is None
        assert info["commit"] is None
        assert info["remote_url"] is None


class TestHasNewCommits:
    def test_same_commit(self, tmp_path):
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."], capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )
        info = get_git_info(tmp_path)
        assert not has_new_commits(tmp_path, info["commit"])

    def test_new_commit(self, tmp_path):
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."], capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )
        old_commit = get_git_info(tmp_path)["commit"]

        (tmp_path / "file2.txt").write_text("world")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "."], capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "second",
             "--author", "Test <test@test.com>"],
            capture_output=True,
        )

        assert has_new_commits(tmp_path, old_commit)


def _make_repo_with_commits(tmp_path):
    """Helper: create a git repo with two commits and a Python file."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "remote", "add", "origin",
         "https://github.com/testorg/testrepo.git"],
        capture_output=True,
    )
    # First commit
    (tmp_path / "main.py").write_text("def hello():\n    return 'v1'\n")
    (tmp_path / "README.md").write_text("# Test")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "initial",
         "--author", "Test <test@test.com>"],
        capture_output=True,
    )
    first_commit = get_git_info(tmp_path)["commit"]

    # Second commit
    (tmp_path / "main.py").write_text("def hello():\n    return 'v2'\n")
    (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "add utils",
         "--author", "Test <test@test.com>"],
        capture_output=True,
    )
    second_commit = get_git_info(tmp_path)["commit"]

    return first_commit, second_commit


class TestResolveCommit:
    def test_resolve_full_sha(self, tmp_path):
        first, _ = _make_repo_with_commits(tmp_path)
        assert resolve_commit(tmp_path, first) == first

    def test_resolve_short_sha(self, tmp_path):
        first, _ = _make_repo_with_commits(tmp_path)
        resolved = resolve_commit(tmp_path, first[:7])
        assert resolved == first

    def test_resolve_head(self, tmp_path):
        _, second = _make_repo_with_commits(tmp_path)
        assert resolve_commit(tmp_path, "HEAD") == second

    def test_resolve_invalid(self, tmp_path):
        _make_repo_with_commits(tmp_path)
        assert resolve_commit(tmp_path, "nonexistent_ref_xyz") is None


class TestListFilesAtCommit:
    def test_first_commit(self, tmp_path):
        first, _ = _make_repo_with_commits(tmp_path)
        files = list_files_at_commit(tmp_path, first)
        assert "main.py" in files
        assert "README.md" in files
        assert "utils.py" not in files  # added in second commit

    def test_second_commit(self, tmp_path):
        _, second = _make_repo_with_commits(tmp_path)
        files = list_files_at_commit(tmp_path, second)
        assert "main.py" in files
        assert "utils.py" in files

    def test_invalid_commit(self, tmp_path):
        _make_repo_with_commits(tmp_path)
        files = list_files_at_commit(tmp_path, "0" * 40)
        assert files == []


class TestGetFileAtCommit:
    def test_get_file_v1(self, tmp_path):
        first, _ = _make_repo_with_commits(tmp_path)
        content = get_file_at_commit(tmp_path, first, "main.py")
        assert "return 'v1'" in content

    def test_get_file_v2(self, tmp_path):
        _, second = _make_repo_with_commits(tmp_path)
        content = get_file_at_commit(tmp_path, second, "main.py")
        assert "return 'v2'" in content

    def test_file_not_in_commit(self, tmp_path):
        first, _ = _make_repo_with_commits(tmp_path)
        content = get_file_at_commit(tmp_path, first, "utils.py")
        assert content is None

    def test_nonexistent_file(self, tmp_path):
        _, second = _make_repo_with_commits(tmp_path)
        content = get_file_at_commit(tmp_path, second, "nope.py")
        assert content is None


class TestGetCommitInfo:
    def test_valid_commit(self, tmp_path):
        first, _ = _make_repo_with_commits(tmp_path)
        info = get_commit_info(tmp_path, first)
        assert info is not None
        assert info["sha"] == first
        assert len(info["short_sha"]) >= 7
        assert info["message"] == "initial"
        assert info["author"] == "Test"
        assert info["date"]  # ISO format date

    def test_invalid_commit(self, tmp_path):
        _make_repo_with_commits(tmp_path)
        info = get_commit_info(tmp_path, "0" * 40)
        assert info is None


class TestMergeBase:
    def test_merge_base_same_branch(self, tmp_path):
        first, second = _make_repo_with_commits(tmp_path)
        base = get_merge_base(tmp_path, first, second)
        assert base == first

    def test_merge_base_invalid(self, tmp_path):
        _make_repo_with_commits(tmp_path)
        base = get_merge_base(tmp_path, "0" * 40, "HEAD")
        assert base is None


class TestChangedFilesBetween:
    def test_changed_files(self, tmp_path):
        first, second = _make_repo_with_commits(tmp_path)
        changed = get_changed_files_between(tmp_path, first, second)
        assert "main.py" in changed  # modified
        assert "utils.py" in changed  # added

    def test_no_changes(self, tmp_path):
        _, second = _make_repo_with_commits(tmp_path)
        changed = get_changed_files_between(tmp_path, second, second)
        assert changed == []
