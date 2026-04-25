import json
import pytest
from pathlib import Path
from gitrelay.config import MainConfig, LocalHubsConfig, LocalHubConfig


@pytest.fixture
def test_tool_path(tmp_path):
    """Provides a temporary path for MainConfig and cleans up after."""
    path = tmp_path / "tool.json"
    # Mock the get_config_path to use our temp path
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


def test_load_raises_not_found(test_tool_path):
    """Verifies that load() raises FileNotFoundError if config is missing."""
    with pytest.raises(FileNotFoundError):
        MainConfig.load()


def test_load_raises_json_error(test_tool_path):
    """Verifies that load() raises JSONDecodeError if JSON is malformed."""
    test_tool_path.write_text("{ invalid json")
    with pytest.raises(json.JSONDecodeError):
        MainConfig.load()


def test_load_raises_validation_error(test_tool_path):
    """Verifies that load() raises ValidationError if data is invalid."""
    # default_local_repo_sync_interval_secs should be an int
    test_tool_path.write_text(
        json.dumps({"default_local_repo_sync_interval_secs": "not an int"})
    )
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        MainConfig.load()


def test_tool_config_save_load(test_tool_path):
    """Verifies saving and loading MainConfig."""
    config = MainConfig()
    config.default_local_repo_sync_interval_secs = 7200
    config.save()

    assert test_tool_path.exists()

    # Verify content via raw JSON
    with open(test_tool_path, "r") as f:
        data = json.load(f)
        assert data["default_local_repo_sync_interval_secs"] == 7200
        assert data["local_hubs_dir"] == "~/githubs"

    # Verify content via load()
    loaded = MainConfig.load()
    assert loaded.default_local_repo_sync_interval_secs == 7200
    assert loaded.local_hubs_dir == Path("~/githubs")


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
    assert isinstance(loaded.local_hubs[0], LocalHubConfig)
