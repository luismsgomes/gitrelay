import os
import subprocess
import sys

import pytest


@pytest.fixture
def mock_home(tmp_path):
    """Provides a fresh, isolated home directory for integration testing."""
    return tmp_path


def test_hub_init_integration(mock_home):
    """Verifies that 'gitrelay hub init NAME' creates a bare git repository."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    # 1. First init config to establish local_hubs_dir
    subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "config", "init"],
        check=True,
        env=env,
    )

    # 2. Initialize a hub
    hub_name = "test-hub"
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    assert f"Successfully initialized hub: {hub_name}" in result.stdout

    # 3. Verify the hub exists and is bare
    # Default hub dir is ~/githubs
    hub_path = mock_home / "githubs" / f"{hub_name}.git"
    assert hub_path.exists()
    assert (hub_path / "config").exists()
    assert (hub_path / "HEAD").exists()

    # Check if it's actually bare
    res = subprocess.run(
        ["git", "-C", str(hub_path), "rev-parse", "--is-bare-repository"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "true"
