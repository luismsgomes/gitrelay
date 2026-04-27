"""
Integration test suite for Git Relay systemd integration.

This module verifies the end-to-end integration between the Git Relay CLI,
systemd, and the background daemon in a real context using Simulator Mode.

APPROACH:
1.  Isolation: All tests use the environment variable 'GITRELAY_SERVICE_NAME'
    (set to 'gitrelay-test') to ensure that the test does not interfere with
    the real gitrelay service that may be running.
2.  Simulator Mode: We use the real gitrelay executable with the '--dry-run'
    flag. This tells the daemon to load configuration and schedule jobs but
    skip actual repository synchronization, logging its intent instead.
3.  Initialization: Before installing the service, we run 'config init' to
    ensure a valid configuration exists in the test environment, preventing
    startup crashes.
4.  Real Context: Tests are performed in the user's real $HOME environment,
    communicating with the real systemd user manager and journalctl, providing
    maximum realism while maintaining safety through service isolation.

TESTED SCENARIOS:
- Service installation ('daemon install --dry-run') and unit file verification.
- Service lifecycle management ('start', 'stop', 'restart').
- Service configuration ('enable', 'disable').
- Observability ('status', 'logs').
- Service uninstallation ('daemon uninstall').
"""

# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import os
import shutil
import subprocess
import time
import sys
from datetime import datetime
import pytest
from pathlib import Path

TEST_SERVICE_NAME = "gitrelay-test"

# Core content of expected log tokens
START_MESSAGE = "Daemon starting..."
STOP_MESSAGE = "Daemon stopping (received SIGTERM)"


@pytest.fixture(autouse=True)
def systemd_env(monkeypatch):
    """Sets up the test service name for all tests in this module."""
    monkeypatch.setenv("GITRELAY_SERVICE_NAME", TEST_SERVICE_NAME)
    return TEST_SERVICE_NAME


@pytest.fixture
def cleanup_service(systemd_env):
    """Ensures the test service is removed even if the test fails."""
    yield
    # Cleanup after test
    if shutil.which("systemctl"):
        subprocess.run(
            ["systemctl", "--user", "stop", f"{TEST_SERVICE_NAME}.service"],
            capture_output=True,
        )
        subprocess.run(
            ["systemctl", "--user", "disable", f"{TEST_SERVICE_NAME}.service"],
            capture_output=True,
        )

    service_path = (
        Path("~/.config/systemd/user").expanduser() / f"{TEST_SERVICE_NAME}.service"
    )
    if service_path.exists():
        service_path.unlink()

    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)


# --- Unit-style Integration Tests (Always run) ---


def test_install_systemd_service_logic(tmp_path):
    """Verifies systemd unit creation and command orchestration using mocks."""
    from unittest.mock import patch

    from gitrelay.systemd import install_service

    mock_config_dir = tmp_path / "systemd" / "user"
    mock_config_dir.mkdir(parents=True)
    exe_path = "/usr/bin/gitrelay"
    service_file = mock_config_dir / f"{TEST_SERVICE_NAME}.service"

    with (
        patch("gitrelay.main.get_executable_path", return_value=exe_path),
        patch("gitrelay.systemd.Path.expanduser", return_value=mock_config_dir),
        patch("gitrelay.systemd.daemon_reload"),
        patch("gitrelay.systemd.enable_service"),
    ):

        assert install_service(dry_run=True) is True
        assert service_file.exists()
        content = service_file.read_text()

        # Verify the pattern: "/path/to/gitrelay" daemon run --dry-run
        assert f'ExecStart="{exe_path}" daemon run --dry-run' in content


def test_uninstall_systemd_service_logic(tmp_path):
    """Verifies service cleanup orchestration using mocks."""
    from unittest.mock import patch

    from gitrelay.systemd import uninstall_service

    mock_config_dir = tmp_path / "systemd" / "user"
    mock_config_dir.mkdir(parents=True)
    service_file = mock_config_dir / f"{TEST_SERVICE_NAME}.service"
    service_file.touch()

    with (
        patch("gitrelay.systemd.Path.expanduser", return_value=mock_config_dir),
        patch("gitrelay.systemd.disable_service") as mock_disable,
        patch("gitrelay.systemd.daemon_reload") as mock_reload,
    ):
        assert uninstall_service() is True
        assert not service_file.exists()
        assert mock_disable.called
        assert mock_reload.called


# --- Real-world Integration Tests (Skip if no systemctl) ---


def test_systemd_install_and_lifecycle(cleanup_service, systemd_env):
    """
    End-to-end test of the systemd installation and service lifecycle.
    Uses the real $HOME but with a test-specific service name.

    TEST PLAN:
    0. INITIAL CHECK:
       - Ensure unit file does not exist.
       - Initialize a test configuration using 'config init'.
       - Ensure daemon commands fail with expected error messages.
    1. INSTALL ('daemon install --dry-run'):
       - Verify unit file creation in ~/.config/systemd/user/.
    2. STATUS ('daemon status'):
       - Verify 'active (running)'.
    3. LOGS ('daemon logs'):
       - Verify log contains ["Daemon starting..."].
    4. RESTART ('daemon restart'):
       - Verify the daemon cycles: check for START -> STOP -> START.
    5. STOP ('daemon stop'):
       - Verify log ends with ["Daemon stopping..."].
       - Verify status becomes 'inactive (dead)'.
    6. UNINSTALL ('daemon uninstall'):
       - Verify unit file removal and service disable.
       - Ensure daemon status fails as expected.
    """
    if not shutil.which("systemctl"):
        pytest.skip("systemctl not found, skipping lifecycle test")

    from gitrelay.main import get_executable_path

    exe = get_executable_path()
    service_path = (
        Path("~/.config/systemd/user").expanduser() / f"{TEST_SERVICE_NAME}.service"
    )

    # Capture start time to ignore previous logs
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def filter_logs(output):
        """Helper to extract only our daemon tokens from the log output."""
        tokens = []
        for line in output.splitlines():
            if START_MESSAGE in line:
                tokens.append(START_MESSAGE)
            elif STOP_MESSAGE in line:
                tokens.append(STOP_MESSAGE)
        return tokens

    # 0. INITIAL CHECK & INIT
    assert not service_path.exists()

    # Initialize config so the real daemon doesn't crash
    subprocess.run(
        [exe, "config", "init", "--force"],
        check=True,
    )

    # Force log_level to INFO for testing so we can see the start/stop messages
    from gitrelay.config import MainConfig
    config = MainConfig.load()
    config.log_level = "INFO"
    config.save()

    # Status should show 'could not be found'
    res = subprocess.run(
        [exe, "daemon", "status"],
        capture_output=True,
        text=True,
    )
    assert (
        f"{TEST_SERVICE_NAME}.service could not be found" in res.stdout
        or res.returncode != 0
    )

    # 1. INSTALL
    result = subprocess.run(
        [exe, "daemon", "install", "--dry-run"],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    assert "Successfully installed" in result.stdout

    # VERIFY unit file
    assert service_path.exists(), f"Unit file not found at {service_path}"
    content = service_path.read_text()
    assert "daemon run --dry-run" in content

    # 2. STATUS
    time.sleep(2)
    result = subprocess.run(
        [exe, "daemon", "status"],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    assert "active (running)" in result.stdout

    # 3. LOGS
    result = subprocess.run(
        [
            exe,
            "daemon",
            "logs",
            "--since",
            start_time,
            "--output",
            "cat",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    log_tokens = filter_logs(result.stdout)
    assert log_tokens == [START_MESSAGE]

    # 4. RESTART
    subprocess.run(
        [exe, "daemon", "restart"],
        check=True,
        env=os.environ,
    )
    time.sleep(2)

    # Verify the sequence: START -> STOP -> START
    result = subprocess.run(
        [
            exe,
            "daemon",
            "logs",
            "--since",
            start_time,
            "--output",
            "cat",
        ],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    log_tokens = filter_logs(result.stdout)
    expected_sequence = [START_MESSAGE, STOP_MESSAGE, START_MESSAGE]
    assert log_tokens == expected_sequence

    # 5. STOP
    subprocess.run(
        [exe, "daemon", "stop"],
        check=True,
        env=os.environ,
    )
    time.sleep(1)

    # Verify the sequence ends with STOPPED
    result = subprocess.run(
        [
            exe,
            "daemon",
            "logs",
            "--since",
            start_time,
            "--output",
            "cat",
        ],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    log_tokens = filter_logs(result.stdout)
    assert log_tokens[-1] == STOP_MESSAGE

    result = subprocess.run(
        [exe, "daemon", "status"],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert "inactive (dead)" in result.stdout

    # 6. UNINSTALL
    result = subprocess.run(
        [exe, "daemon", "uninstall"],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    assert "Successfully uninstalled" in result.stdout

    # Final meaningful verification
    assert not service_path.exists()
    res = subprocess.run(
        [exe, "daemon", "status"],
        capture_output=True,
        text=True,
    )
    assert (
        f"{TEST_SERVICE_NAME}.service could not be found" in res.stdout
        or res.returncode != 0
    )
