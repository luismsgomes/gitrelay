# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gitrelay.git import (
    GitHookType,
    init_repository,
    install_git_alias,
    install_hook,
    is_bare_repository,
)


def test_install_git_alias():
    with patch("gitrelay.git.subprocess.run") as mock_run:
        install_git_alias()
        mock_run.assert_called_once_with(
            ["git", "config", "--global", "alias.relay", "gitrelay"], check=True
        )


def test_is_bare_repository_true():
    with patch("gitrelay.git.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="true\n")
        assert is_bare_repository(Path("/tmp/fake-bare.git")) is True


def test_is_bare_repository_false():
    with patch("gitrelay.git.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="false\n")
        assert is_bare_repository(Path("/tmp/fake-repo")) is False


def test_is_bare_repository_error():
    with patch("gitrelay.git.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        assert is_bare_repository(Path("/tmp/fake-repo")) is False


def test_init_repository_bare(tmp_path):
    path = tmp_path / "nested" / "new-hub.git"
    with patch("gitrelay.git.subprocess.run") as mock_run:
        init_repository(path)
        assert path.parent.exists()
        mock_run.assert_called_once_with(
            ["git", "init", "--bare", str(path)], check=True
        )


def test_init_repository_non_bare(tmp_path):
    path = tmp_path / "new-repo"
    with patch("gitrelay.git.subprocess.run") as mock_run:
        init_repository(path)
        mock_run.assert_called_once_with(["git", "init", str(path)], check=True)


def test_init_repository_already_exists(tmp_path):
    path = tmp_path / "exists"
    path.mkdir()
    with pytest.raises(FileExistsError):
        init_repository(path)


def test_install_hook_bare(tmp_path):
    repo_path = tmp_path / "bare.git"
    repo_path.mkdir()
    (repo_path / "hooks").mkdir()

    with patch("gitrelay.git.is_bare_repository", return_value=True):
        install_hook(repo_path, GitHookType.POST_RECEIVE, ["hook", "post-receiving"])

    hook_path = repo_path / "hooks" / "post-receive"
    assert hook_path.exists()
    assert (
        hook_path.read_text() == "#!/bin/sh\nexec gitrelay hook post-receiving\n"
    )
    assert (hook_path.stat().st_mode & 0o111) != 0  # Executable


def test_install_hook_non_bare(tmp_path):
    repo_path = tmp_path / "non-bare"
    repo_path.mkdir()
    (repo_path / ".git" / "hooks").mkdir(parents=True)

    with patch("gitrelay.git.is_bare_repository", return_value=False):
        install_hook(repo_path, GitHookType.POST_COMMIT, ["hook", "after-commit"])

    hook_path = repo_path / ".git" / "hooks" / "post-commit"
    assert hook_path.exists()
    assert hook_path.read_text() == "#!/bin/sh\nexec gitrelay hook after-commit\n"


def test_install_hook_not_git_repo(tmp_path):
    path = tmp_path / "not-a-repo"
    path.mkdir()
    with (
        patch("gitrelay.git.is_bare_repository", return_value=False),
        pytest.raises(ValueError, match="Not a git repository"),
    ):
        install_hook(path, GitHookType.POST_RECEIVE, [])
