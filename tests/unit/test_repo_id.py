# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

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


def test_resolve_push_wait_with_id_match_and_path_healing(mock_configs, tmp_path):
    """Verifies that matching by ID works and updates the path if it changed."""
    _, _, repos_dir = mock_configs
    old_path = tmp_path / "old-path"
    new_path = tmp_path / "new-path"
    new_path.mkdir()
    repo_id = "test-uuid"

    # Save individual repo config with old path
    repo_cfg = RepositoryConfig(
        repo_id=repo_id,
        hub_name="test-hub",
        local_repo_path=old_path,
        is_bare=False,
        default_push_relay_wait=False,
    )
    repo_cfg.save()

    # Register in hub
    hubs_config = LocalHubsConfig.load()
    hub_cfg = LocalHubConfig(hub_name="test-hub")
    hub_cfg.add_synced_local_repo_id(repo_id)
    hubs_config.local_hubs.append(hub_cfg)
    hubs_config.save()

    with (
        patch("gitrelay.git.git_get_toplevel", return_value=new_path),
        patch("gitrelay.git.git_get_repo_id", return_value=repo_id),
        patch("gitrelay.git.git_push") as mock_git_push,
    ):
        result = runner.invoke(app, ["push"])
        assert result.exit_code == 0
        mock_git_push.assert_called_once_with("hub", False)

        # Verify self-healing: repo config should be updated to new_path
        updated_cfg = RepositoryConfig.load(repo_id)
        assert updated_cfg.local_repo_path.absolute() == new_path.absolute()


def test_resolve_push_wait_id_migration(mock_configs, tmp_path):
    """Verifies that git config ID is updated if path matches a repo config file."""
    _, _, _ = mock_configs
    repo_path = tmp_path / "my-repo"
    repo_path.mkdir()
    repo_id = "existing-uuid-in-json"

    # Config file exists, but git config is empty
    repo_cfg = RepositoryConfig(
        repo_id=repo_id,
        hub_name="test-hub",
        local_repo_path=repo_path,
        is_bare=False,
    )
    repo_cfg.save()

    with (
        patch("gitrelay.git.git_get_toplevel", return_value=repo_path),
        patch("gitrelay.git.git_get_repo_id", return_value=None),
        patch("gitrelay.git.git_set_repo_id") as mock_set_id,
        patch("gitrelay.git.git_push"),
    ):
        runner.invoke(app, ["push"])

        # Verify migration: ID should be set in git config
        mock_set_id.assert_called_once_with(repo_path.absolute(), repo_id)
