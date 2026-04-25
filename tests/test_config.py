import json
import pytest
import time
from pathlib import Path
from gitrelay.config import MainConfig, LocalHubsConfig, LocalHubConfig


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
