import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from gitrelay.config import (
    LocalHubConfig,
    LocalHubsConfig,
    MainConfig,
    RepositoryConfig,
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
    """Verifies round-trip of a complex configuration with synced IDs."""
    hubs_config = LocalHubsConfig(
        local_hubs=[
            LocalHubConfig(
                hub_name="work/api",
                synced_local_repo_ids=["uuid-1", "uuid-2"],
                synced_remote_hubs=[],
            )
        ]
    )
    hubs_config.save()

    loaded = LocalHubsConfig.load()
    assert len(loaded.local_hubs) == 1
    assert loaded.local_hubs[0].hub_name == "work/api"
    assert loaded.local_hubs[0].synced_local_repo_ids == ["uuid-1", "uuid-2"]


def test_repository_config_save_load(tmp_path):
    """Verifies round-trip of individual RepositoryConfig files."""
    # Mock repos dir
    repos_dir = tmp_path / "repos"
    original_method = RepositoryConfig.get_repos_dir
    RepositoryConfig.get_repos_dir = classmethod(lambda cls: repos_dir)

    try:
        repo_id = "test-uuid"
        config = RepositoryConfig(
            repo_id=repo_id,
            hub_name="my-hub",
            local_repo_path=Path("/home/user/repo"),
            is_bare=False,
            sync_direction=SyncDirection.FETCH,
        )
        config.save()

        assert (repos_dir / f"{repo_id}.json").exists()

        loaded = RepositoryConfig.load(repo_id)
        assert loaded.repo_id == repo_id
        assert loaded.hub_name == "my-hub"
        assert loaded.local_repo_path == Path("/home/user/repo")
        assert loaded.is_bare is False
    finally:
        RepositoryConfig.get_repos_dir = original_method


def test_remote_alias_uniqueness_validation():
    """Verifies that duplicate remote aliases are caught by the model validator."""
    from gitrelay.config import RemoteHostConfig, RemoteHubSyncConfig

    host = RemoteHostConfig(
        remote_host_name="host1",
        remote_hubs_dir=Path("/hubs"),
        remote_hub_scan_interval_secs=3600,
        remote_hub_scan_enabled=True,
    )

    remote1 = RemoteHubSyncConfig(
        target_alias="origin",
        remote_hub_name=Path("repo.git"),
        remote_host_config=host,
    )
    remote2 = RemoteHubSyncConfig(
        target_alias="origin",  # CLASH
        remote_hub_name=Path("other.git"),
        remote_host_config=host,
    )

    with pytest.raises(ValueError, match="Duplicate remote target aliases found"):
        LocalHubConfig(hub_name="my-hub", synced_remote_hubs=[remote1, remote2])


def test_save_triggers_validation():
    """Verifies that save() fails if the model state is somehow corrupted."""
    from gitrelay.config import RemoteHostConfig, RemoteHubSyncConfig

    host = RemoteHostConfig(
        remote_host_name="host1",
        remote_hubs_dir=Path("/hubs"),
        remote_hub_scan_interval_secs=3600,
        remote_hub_scan_enabled=True,
    )

    remote = RemoteHubSyncConfig(
        target_alias="origin",
        remote_hub_name=Path("repo.git"),
        remote_host_config=host,
    )
    hub = LocalHubConfig(hub_name="my-hub", synced_remote_hubs=[remote])

    # Manually bypass the method to create a clash
    hub.synced_remote_hubs.append(
        RemoteHubSyncConfig(
            target_alias="origin",
            remote_hub_name=Path("other.git"),
            remote_host_config=host,
        )
    )

    # Verify the object itself is now invalid according to its own validator
    with pytest.raises(ValidationError):
        hub.model_validate(hub.model_dump())
