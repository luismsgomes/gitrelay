# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from gitrelay.config import (
    LocalHubConfig,
    LocalHubsConfig,
    MainConfig,
    RepositoryConfig,
)
from gitrelay.main import app

runner = CliRunner()


@pytest.fixture
def mock_configs(tmp_path):
    """Mocks all configuration paths to use a temporary directory."""
    main_path = tmp_path / "main.json"
    hubs_path = tmp_path / "hubs.json"
    repos_dir = tmp_path / "repos"

    with (
        patch("gitrelay.config.MainConfig.get_config_path", return_value=main_path),
        patch(
            "gitrelay.config.LocalHubsConfig.get_config_path", return_value=hubs_path
        ),
        patch("gitrelay.config.RepositoryConfig.get_repos_dir", return_value=repos_dir),
    ):
        MainConfig().save()
        LocalHubsConfig().save()
        yield main_path, hubs_path, repos_dir


def test_push_wait_resolution_default(mock_configs):
    """Verifies that the default 'wait' from MainConfig is used."""
    with (
        patch("gitrelay.git.git_get_toplevel", return_value=Path("/repo")),
        patch("gitrelay.git.git_get_repo_id", return_value=None),
        patch("gitrelay.git.git_push") as mock_git_push,
    ):
        result = runner.invoke(app, ["push"])
        assert result.exit_code == 0
        # Default in MainConfig is True
        mock_git_push.assert_called_once_with("hub", True)


def test_push_wait_resolution_target_override(mock_configs, tmp_path):
    """Verifies that target-level override is respected."""
    _, _, _ = mock_configs
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    repo_id = "test-uuid"

    # 1. Setup individual RepositoryConfig
    repo_cfg = RepositoryConfig(
        repo_id=repo_id,
        hub_name="test-hub",
        local_repo_path=repo_path,
        is_bare=False,
        default_push_relay_wait=False,
    )
    repo_cfg.save()

    # 2. Setup Hub Config
    hubs_config = LocalHubsConfig.load()
    hub_cfg = LocalHubConfig(hub_name="test-hub", default_push_relay_wait=True)
    hub_cfg.add_synced_local_repo_id(repo_id)
    hubs_config.local_hubs.append(hub_cfg)
    hubs_config.save()

    with (
        patch("gitrelay.git.git_get_toplevel", return_value=repo_path),
        patch("gitrelay.git.git_get_repo_id", return_value=repo_id),
        patch("gitrelay.git.git_push") as mock_git_push,
    ):
        result = runner.invoke(app, ["push"])
        assert result.exit_code == 0
        mock_git_push.assert_called_once_with("hub", False)


def test_push_wait_resolution_hub_override(mock_configs, tmp_path):
    """Verifies that hub-level override is used when target has no override."""
    _, _, _ = mock_configs
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    repo_id = "test-uuid"

    # 1. Setup individual RepositoryConfig (no override)
    repo_cfg = RepositoryConfig(
        repo_id=repo_id,
        hub_name="test-hub",
        local_repo_path=repo_path,
        is_bare=False,
        default_push_relay_wait=None,
    )
    repo_cfg.save()

    # 2. Setup Hub Config (with override)
    hubs_config = LocalHubsConfig.load()
    hub_cfg = LocalHubConfig(hub_name="test-hub", default_push_relay_wait=False)
    hub_cfg.add_synced_local_repo_id(repo_id)
    hubs_config.local_hubs.append(hub_cfg)
    hubs_config.save()

    with (
        patch("gitrelay.git.git_get_toplevel", return_value=repo_path),
        patch("gitrelay.git.git_get_repo_id", return_value=repo_id),
        patch("gitrelay.git.git_push") as mock_git_push,
    ):
        result = runner.invoke(app, ["push"])
        assert result.exit_code == 0
        mock_git_push.assert_called_once_with("hub", False)


def test_push_cli_flag_override(mock_configs):
    """Verifies that CLI flags (--no-wait) override any config."""
    with (
        patch("gitrelay.git.git_get_toplevel", return_value=Path("/repo")),
        patch("gitrelay.git.git_get_repo_id", return_value=None),
        patch("gitrelay.git.git_push") as mock_git_push,
    ):
        result = runner.invoke(app, ["push", "--no-wait"])
        assert result.exit_code == 0
        mock_git_push.assert_called_once_with("hub", False)


def test_push_custom_remote(mock_configs):
    """Verifies that custom remote name can be passed."""
    with (
        patch("gitrelay.git.git_get_toplevel", return_value=Path("/repo")),
        patch("gitrelay.git.git_get_repo_id", return_value=None),
        patch("gitrelay.git.git_push") as mock_git_push,
    ):
        result = runner.invoke(app, ["push", "origin"])
        assert result.exit_code == 0
        mock_git_push.assert_called_once_with("origin", True)
