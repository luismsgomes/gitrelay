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


def test_hub_init_already_exists(mock_home):
    """Verifies error when trying to init a hub that already exists."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    subprocess.run([sys.executable, "-m", "gitrelay.main", "config", "init"], check=True, env=env)

    hub_name = "duplicate-hub"
    # 1. First init (success)
    subprocess.run([sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name], check=True, env=env)

    # 2. Second init (fail)
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name],
        capture_output=True, text=True, env=env
    )

    assert result.returncode == 1
    assert "Hub already exists" in result.stdout


def test_hub_delete_with_y_flag(mock_home):
    """Verifies that 'gitrelay hub delete -y NAME' removes the repository and logs."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    # 1. Setup: Init config and a hub
    subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "config", "init"],
        check=True,
        env=env,
    )
    hub_name = "delete-me"
    subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name],
        check=True,
        env=env,
    )
    hub_path = mock_home / "githubs" / f"{hub_name}.git"
    assert hub_path.exists()

    # 2. Create a dummy log file to verify it gets deleted
    log_dir = mock_home / ".cache" / "gitrelay" / "logs" / "sync" / hub_name
    log_dir.mkdir(parents=True)
    log_file = log_dir / "target.jsonl"
    log_file.touch()

    # 3. Run delete with -y
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "delete", "-y", hub_name],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )

    assert f"Successfully deleted hub: {hub_name}" in result.stdout
    assert not hub_path.exists()
    assert not log_dir.exists()


def test_hub_delete_with_long_yes_flag(mock_home):
    """Verifies that 'gitrelay hub delete --yes NAME' removes the repository."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    # 1. Setup: Init config and a hub
    subprocess.run([sys.executable, "-m", "gitrelay.main", "config", "init"], check=True, env=env)
    hub_name = "delete-me-long"
    subprocess.run([sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name], check=True, env=env)
    hub_path = mock_home / "githubs" / f"{hub_name}.git"

    # 2. Run delete with --yes
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "delete", "--yes", hub_name],
        capture_output=True, text=True, check=True, env=env
    )

    assert f"Successfully deleted hub: {hub_name}" in result.stdout
    assert not hub_path.exists()


def test_hub_delete_interactive_confirmed(mock_home):
    """Verifies deletion when user confirms via stdin."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    subprocess.run([sys.executable, "-m", "gitrelay.main", "config", "init"], check=True, env=env)
    hub_name = "interactive-hub"
    subprocess.run([exe := sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name], check=True, env=env)
    hub_path = mock_home / "githubs" / f"{hub_name}.git"

    # Run without -y, but pipe "y" into stdin
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "delete", hub_name],
        input="y\n", capture_output=True, text=True, check=True, env=env
    )

    assert f"Successfully deleted hub: {hub_name}" in result.stdout
    assert not hub_path.exists()


def test_hub_delete_aborted_by_enter(mock_home):
    """Verifies that pressing Enter (defaulting to No) aborts deletion."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    subprocess.run([sys.executable, "-m", "gitrelay.main", "config", "init"], check=True, env=env)
    hub_name = "keep-me"
    subprocess.run([sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name], check=True, env=env)
    hub_path = mock_home / "githubs" / f"{hub_name}.git"

    # Run without -y, and pipe empty input (Enter)
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "delete", hub_name],
        input="\n", capture_output=True, text=True, env=env
    )

    assert result.returncode != 0
    assert "Aborted" in result.stdout or "Aborted" in result.stderr
    assert hub_path.exists()


def test_hub_delete_aborted_by_no(mock_home):
    """Verifies that explicitly typing 'n' aborts deletion."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    subprocess.run([sys.executable, "-m", "gitrelay.main", "config", "init"], check=True, env=env)
    hub_name = "keep-me-explicit"
    subprocess.run([sys.executable, "-m", "gitrelay.main", "hub", "init", hub_name], check=True, env=env)
    hub_path = mock_home / "githubs" / f"{hub_name}.git"

    # Run without -y, and pipe "n"
    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "delete", hub_name],
        input="n\n", capture_output=True, text=True, env=env
    )

    assert result.returncode != 0
    assert "Aborted" in result.stdout or "Aborted" in result.stderr
    assert hub_path.exists()


def test_hub_delete_not_found(mock_home):
    """Verifies error when hub does not exist."""
    env = os.environ.copy()
    env["HOME"] = str(mock_home)

    subprocess.run([sys.executable, "-m", "gitrelay.main", "config", "init"], check=True, env=env)

    result = subprocess.run(
        [sys.executable, "-m", "gitrelay.main", "hub", "delete", "-y", "non-existent"],
        capture_output=True, text=True, env=env
    )

    assert result.returncode == 1
    assert "Hub 'non-existent' not found" in result.stdout
