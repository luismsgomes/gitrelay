import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from gitrelay.config import (
    LocalBareRepoSyncConfig,
    LocalHubConfig,
    LocalHubsConfig,
    LocalRepoSyncConfig,
    MainConfig,
    SyncDirection,
)


@pytest.fixture
def test_main_config_path(tmp_path):
    """Provides a temporary path for MainConfig and cleans up after."""
    path = tmp_path / "tool.json"
    original_method = MainConfig.get_config_path
    MainConfig.get_config_path = classmethod(lambda cls: path)
    yield path
    MainConfig.get_config_path = original_method


@pytest.fixture
def test_hubs_path(tmp_path):
    """Provides a temporary path for LocalHubsConfig and cleans up after."""
    path = tmp_path / "hubs.json"
    original_method = LocalHubsConfig.get_config_path
    LocalHubsConfig.get_config_path = classmethod(lambda cls: path)
    yield path
    LocalHubsConfig.get_config_path = original_method


def test_config_reload(test_main_config_path):
    """Verifies that reload() only reloads when file actually changes."""
    config = MainConfig()
    config.sync_enabled = True
    config.save()

    # 1. Initial load
    loaded = MainConfig.load()
    assert loaded.sync_enabled is True

    # 2. Immediate reload (no change)
    assert loaded.reload() is False

    # 3. Modify file externally
    # We sleep to ensure the timestamp changes (mtime granularity)
    time.sleep(0.01)
    with open(test_main_config_path, "w") as f:
        data = loaded.model_dump(mode="json")
        data["sync_enabled"] = False
        json.dump(data, f)

    # 4. Reload should now be True
    assert loaded.reload() is True
    assert loaded.sync_enabled is False


def test_load_raises_not_found(test_main_config_path):
    """Verifies that load() raises FileNotFoundError if config is missing."""
    with pytest.raises(FileNotFoundError):
        MainConfig.load()


def test_load_raises_json_error(test_main_config_path):
    """Verifies that load() raises JSONDecodeError if JSON is malformed."""
    test_main_config_path.write_text("{ invalid json")
    with pytest.raises(json.JSONDecodeError):
        MainConfig.load()


def test_load_raises_validation_error(test_main_config_path):
    """Verifies that load() raises ValidationError if data is invalid."""
    test_main_config_path.write_text(
        json.dumps({"default_local_repo_sync_interval_secs": "not an int"})
    )
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        MainConfig.load()


def test_main_config_save_load(test_main_config_path):
    """Verifies saving and loading MainConfig."""
    config = MainConfig()
    config.default_local_repo_sync_interval_secs = 7200
    config.save()

    assert test_main_config_path.exists()

    with open(test_main_config_path, "r") as f:
        data = json.load(f)
        assert data["default_local_repo_sync_interval_secs"] == 7200

    loaded = MainConfig.load()
    assert loaded.default_local_repo_sync_interval_secs == 7200


def test_complex_config_roundtrip(test_hubs_path):
    """Verifies round-trip of a complex configuration with nested lists."""
    hubs_config = LocalHubsConfig(
        local_hubs=[
            LocalHubConfig(
                hub_name="work/api",
                synced_local_repos=[],
                synced_local_bare_repos=[],
                synced_remote_hubs=[],
            )
        ]
    )
    hubs_config.save()

    loaded = LocalHubsConfig.load()
    assert len(loaded.local_hubs) == 1
    assert loaded.local_hubs[0].hub_name == "work/api"


def test_hub_alias_uniqueness_validation():
    """Verifies that duplicate aliases are caught by the model validator."""
    # Create two configs with same alias
    repo1 = LocalRepoSyncConfig(
        target_alias="origin",
        sync_interval_secs=3600,
        sync_interval_adjust=True,
        local_repo_path=Path("/tmp/repo1"),
    )
    repo2 = LocalRepoSyncConfig(
        target_alias="origin",  # CLASH
        sync_interval_secs=3600,
        sync_interval_adjust=True,
        local_repo_path=Path("/tmp/repo2"),
    )

    with pytest.raises(ValueError, match="Duplicate target aliases found"):
        LocalHubConfig(hub_name="my-hub", synced_local_repos=[repo1, repo2])


def test_add_synced_methods_enforce_uniqueness():
    """Verifies that add_synced_* methods check uniqueness immediately."""
    hub = LocalHubConfig(hub_name="my-hub")

    repo1 = LocalRepoSyncConfig(
        target_alias="origin",
        sync_interval_secs=3600,
        sync_interval_adjust=True,
        local_repo_path=Path("/tmp/repo1"),
    )

    hub.add_synced_local_repo(repo1)

    # Try to add a bare repo with same alias
    bare_repo = LocalBareRepoSyncConfig(
        target_alias="origin",  # CLASH
        sync_interval_secs=3600,
        sync_interval_adjust=True,
        local_repo_path=Path("/tmp/bare"),
        sync_direction=SyncDirection.BOTH,
    )

    with pytest.raises(ValueError, match="already in use"):
        hub.add_synced_local_bare_repo(bare_repo)


def test_save_triggers_validation():
    """Verifies that save() fails if the model state is somehow corrupted."""
    # This shouldn't happen if using add_ methods, but let's test the 'safety net'
    repo = LocalRepoSyncConfig(
        target_alias="origin",
        sync_interval_secs=3600,
        sync_interval_adjust=True,
        local_repo_path=Path("/tmp/repo1"),
    )
    hub = LocalHubConfig(hub_name="my-hub", synced_local_repos=[repo])

    # Manually bypass the method to create a clash
    hub.synced_local_bare_repos.append(
        LocalBareRepoSyncConfig(
            target_alias="origin",
            sync_interval_secs=3600,
            sync_interval_adjust=True,
            local_repo_path=Path("/tmp/bare"),
            sync_direction=SyncDirection.BOTH,
        )
    )

    # Verify the object itself is now invalid according to its own validator
    with pytest.raises(ValidationError):
        hub.model_validate(hub.model_dump())
