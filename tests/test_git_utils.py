"""Tests for git utilities."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from arrow.git_utils import get_git_info, has_new_commits, is_git_repo, parse_remote_url


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
