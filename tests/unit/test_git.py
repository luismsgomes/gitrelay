# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import os
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gitrelay.git import (
    GitHookType,
    git_get_toplevel,
    git_push,
    init_repository,
    install_git_alias,
    install_hook,
    is_bare_repository,
)


def test_git_get_toplevel():
    with patch("gitrelay.git.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="/path/to/repo\n")
        assert git_get_toplevel() == Path("/path/to/repo")
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )


def test_git_push_wait_true():
    with patch("gitrelay.git.subprocess.run") as mock_run:
        git_push("hub", True)
        args, kwargs = mock_run.call_args
        assert args[0] == ["git", "push", "hub"]
        assert kwargs["env"]["GITRELAY_HOOK_WAIT"] == "true"


def test_git_push_wait_false():
    with patch("gitrelay.git.subprocess.run") as mock_run:
        git_push("hub", False)
        args, kwargs = mock_run.call_args
        assert args[0] == ["git", "push", "hub"]
        assert kwargs["env"]["GITRELAY_HOOK_WAIT"] == "false"


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


def test_install_hook_behavior(tmp_path):
    """Verifies that the installed hook behaves correctly (foreground vs background)."""
    repo_path = tmp_path / "behavior.git"
    repo_path.mkdir()
    (repo_path / "hooks").mkdir()

    # 1. Create dummy gitrelay that records its execution
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    dummy_gitrelay = bin_dir / "gitrelay"
    marker_file = tmp_path / "marker"

    # Dummy gitrelay writes "START", sleeps, then writes "END"
    dummy_gitrelay.write_text(
        f"#!/bin/sh\n"
        f'echo "START $@" >> {marker_file}\n'
        f"sleep 0.3\n"
        f'echo "END" >> {marker_file}\n'
    )
    dummy_gitrelay.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    # 2. Install the hook
    with patch("gitrelay.git.is_bare_repository", return_value=True):
        install_hook(repo_path, GitHookType.POST_RECEIVE, ["hook", "post-receiving"])

    hook_script = repo_path / "hooks" / "post-receive"
    assert hook_script.exists()

    # 3. Test WAIT mode (default) -> Foreground
    start_time = time.time()
    subprocess.run([str(hook_script)], env=env, check=True)
    duration = time.time() - start_time

    assert duration >= 0.3
    content = marker_file.read_text()
    assert "START hook post-receiving" in content
    assert "END" in content

    # 4. Test NO-WAIT mode -> Background
    marker_file.write_text("")  # Reset marker
    env["GITRELAY_HOOK_WAIT"] = "false"

    start_time = time.time()
    subprocess.run([str(hook_script)], env=env, check=True)
    duration = time.time() - start_time

    # Should return almost immediately
    assert duration < 0.2

    # Wait for the background process to finish writing to marker
    time.sleep(0.5)
    content = marker_file.read_text()
    assert "START hook post-receiving" in content
    assert "END" in content


def test_install_hook_not_git_repo(tmp_path):
    path = tmp_path / "not-a-repo"
    path.mkdir()
    with (
        patch("gitrelay.git.is_bare_repository", return_value=False),
        pytest.raises(ValueError, match="Not a git repository"),
    ):
        install_hook(path, GitHookType.POST_RECEIVE, [])
