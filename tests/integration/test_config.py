import os
import subprocess
import sys

import pytest

from gitrelay.config import HostsConfig, LocalHubsConfig, MainConfig


@pytest.fixture
def mock_home(tmp_path):
    """Provides a fresh, isolated home directory for integration testing."""
    return tmp_path


def test_config_init_integration(mock_home):
    """
    Verifies that 'gitrelay config init' creates all expected configuration
    files and that they are valid according to our Pydantic models.
    """
    # 1. Setup environment
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    # 2. Run the command
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "config", "init"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    # 3. Verify console output
    assert "Successfully initialized Main configuration" in result.stdout
    assert "Successfully initialized Local hubs configuration" in result.stdout
    assert "Successfully initialized Remote hosts configuration" in result.stdout

    # 4. Verify files exist in the mock home
    config_dir = mock_home / ".config" / "gitrelay"
    assert config_dir.exists()

    main_file = config_dir / "main.json"
    hubs_file = config_dir / "local-hubs.json"
    hosts_file = config_dir / "remote-hosts.json"

    assert main_file.exists()
    assert hubs_file.exists()
    assert hosts_file.exists()

    # 5. Verify file contents by loading them with the real classes
    # We monkeypatch the config paths to point to our mock home
    # so that the .load() method works correctly.
    with (
        pytest.MonkeyPatch().context() as mp,
    ):
        mp.setenv("HOME", str(mock_home))

        # Load the newly created files
        loaded_main = MainConfig.load()
        loaded_hubs = LocalHubsConfig.load()
        loaded_hosts = HostsConfig.load()

        # Compare with fresh default instances
        assert loaded_main.model_dump() == MainConfig().model_dump()
        assert loaded_hubs.model_dump() == LocalHubsConfig().model_dump()
        assert loaded_hosts.model_dump() == HostsConfig().model_dump()


def test_config_init_force_flag(mock_home):
    """Verifies that --force correctly overwrites existing files."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    config_dir = mock_home / ".config" / "gitrelay"
    config_dir.mkdir(parents=True)

    main_file = config_dir / "main.json"
    main_file.write_text("INVALID JSON")

    # 1. Run without force - should show warning
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "config", "init"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert "Main configuration already exists" in result.stdout
    assert main_file.read_text() == "INVALID JSON"

    # 2. Run with force - should overwrite
    subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "config", "init", "--force"],
        check=True,
        env=env,
    )

    # Reload and verify it is now valid JSON/model
    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("HOME", str(mock_home))
        loaded_main = MainConfig.load()
        assert loaded_main.sync_enabled is True
