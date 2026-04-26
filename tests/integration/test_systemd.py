"""
Integration test suite for Git Relay systemd integration.

This module verifies the end-to-end integration between the Git Relay,
systemd, and the background daemon in a real context.

APPROACH:
1.  Isolation: All tests use the environment variable 'GITRELAY_SERVICE_NAME'
    (set to 'gitrelay-test') to ensure that the test does not interfere with
    the real gitrelay service that may be running.
2.  Mock Script: We use 'tests/integration/mock_gitrelay.py' as the entry
    point for integration tests. This script imports the real gitrelay modules
    but patches the daemon loop to allow for deterministic testing.
    Since this mock script does not load or save any configuration, the
    user's real configuration files remain untouched during testing.
3.  Direct Execution: The integration tests invoke the mock_gitrelay.py script
    directly via subprocess (e.g., 'python3 mock_gitrelay.py daemon install').
    This ensures that the generated systemd unit file automatically points
    to mock_gitrelay.py instead of the real gitrelay executable.
4.  Real Context: Tests are performed in the user's real $HOME environment,
    communicating with the real systemd user manager and journalctl, providing
    maximum realism while maintaining safety through service isolation.

TESTED SCENARIOS:
- Service installation ('daemon install') and unit file verification.
- Service lifecycle management ('start', 'stop', 'restart').
- Service configuration ('enable', 'disable').
- Observability ('status', 'logs').
- Service uninstallation ('daemon uninstall').
"""

# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import os
import subprocess
import shutil
import time
import sys
from datetime import datetime
import pytest
from pathlib import Path
from unittest.mock import patch
from gitrelay.systemd import (
    install_service,
    uninstall_service,
)

TEST_SERVICE_NAME = "gitrelay-test"


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
    # We still use tmp_path for the unit file location MOCK to keep it fast
    mock_config_dir = tmp_path / "systemd" / "user"
    mock_config_dir.mkdir(parents=True)
    exe_path = "/usr/bin/gitrelay"
    python_exe = "/usr/bin/python3"
    service_file = mock_config_dir / f"{TEST_SERVICE_NAME}.service"

    with (
        patch("gitrelay.main.get_executable_path", return_value=exe_path),
        patch("gitrelay.systemd.sys.executable", python_exe),
        patch("gitrelay.systemd.Path.expanduser", return_value=mock_config_dir),
        patch("gitrelay.systemd.daemon_reload"),
        patch("gitrelay.systemd.enable_service"),
    ):

        assert install_service() is True
        assert service_file.exists()
        content = service_file.read_text()

        # Verify the new structure: separate interpreter and script
        assert f'ExecStart="{python_exe}" "{exe_path}" daemon run' in content


def test_uninstall_systemd_service_logic(tmp_path):
    """Verifies service cleanup orchestration using mocks."""
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
       - Ensure daemon commands fail with expected error messages.
    1. INSTALL ('daemon install'):
       - Verify unit file creation in ~/.config/systemd/user/.
       - Verify python_exe and script_path separation.
    2. STATUS ('daemon status'):
       - Verify 'active (running)'.
    3. LOGS ('daemon logs'):
       - Verify log is exactly ["MOCK_DAEMON_STARTING"].
    4. RESTART ('daemon restart'):
       - Verify the daemon cycles: check for STARTING -> STOPPED -> STARTING.
    5. STOP ('daemon stop'):
       - Verify log ends with ["MOCK_DAEMON_STOPPED"].
       - Verify status becomes 'inactive (dead)'.
    6. UNINSTALL ('daemon uninstall'):
       - Verify unit file removal and service disable.
       - Ensure daemon status fails as expected.
    """
    if not shutil.which("systemctl"):
        pytest.skip("systemctl not found, skipping lifecycle test")

    # Path to our permanent testing asset
    mock_wrapper_path = Path(__file__).parent / "mock_gitrelay.py"
    service_path = (
        Path("~/.config/systemd/user").expanduser() / f"{TEST_SERVICE_NAME}.service"
    )

    # Capture start time to ignore previous logs
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 0. INITIAL CHECK
    assert not service_path.exists()
    # Status should show 'could not be found'
    res = subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "status"],
        capture_output=True,
        text=True,
    )
    assert (
        f"{TEST_SERVICE_NAME}.service could not be found" in res.stdout
        or res.returncode != 0
    )
    # Logs should be empty or show "-- No entries --"
    res = subprocess.run(
        [
            sys.executable,
            str(mock_wrapper_path),
            "daemon",
            "logs",
            "--since",
            start_time,
            "--output",
            "cat",
        ],
        capture_output=True,
        text=True,
    )
    output = res.stdout.strip()
    assert not output or "-- No entries --" in output

    # 1. INSTALL
    result = subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "install"],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    assert "Successfully installed" in result.stdout

    # VERIFY unit file
    assert service_path.exists(), f"Unit file not found at {service_path}"
    content = service_path.read_text()
    assert str(mock_wrapper_path) in content
    assert str(sys.executable) in content

    # 2. STATUS
    time.sleep(2)
    result = subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "status"],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    assert "active (running)" in result.stdout

    # 3. LOGS
    result = subprocess.run(
        [
            sys.executable,
            str(mock_wrapper_path),
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
    # Filter to ignore systemd "Started..." noise
    log_lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("MOCK_DAEMON_")
    ]
    assert log_lines == ["MOCK_DAEMON_STARTING"]

    # 4. RESTART
    subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "restart"],
        check=True,
        env=os.environ,
    )
    time.sleep(2)

    # Verify the sequence: STARTING -> STOPPED -> STARTING
    result = subprocess.run(
        [
            sys.executable,
            str(mock_wrapper_path),
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
    log_lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("MOCK_DAEMON_")
    ]
    expected_sequence = [
        "MOCK_DAEMON_STARTING",
        "MOCK_DAEMON_STOPPED",
        "MOCK_DAEMON_STARTING",
    ]
    assert log_lines == expected_sequence

    # 5. STOP
    subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "stop"],
        check=True,
        env=os.environ,
    )
    time.sleep(1)

    # Verify the sequence: STARTING -> STOPPED -> STARTING -> STOPPED
    result = subprocess.run(
        [
            sys.executable,
            str(mock_wrapper_path),
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
    log_lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("MOCK_DAEMON_")
    ]
    expected_final_sequence = [
        "MOCK_DAEMON_STARTING",
        "MOCK_DAEMON_STOPPED",
        "MOCK_DAEMON_STARTING",
        "MOCK_DAEMON_STOPPED",
    ]
    assert log_lines == expected_final_sequence

    result = subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "status"],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert "inactive (dead)" in result.stdout

    # 6. UNINSTALL
    result = subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "uninstall"],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ,
    )
    assert "Successfully uninstalled" in result.stdout

    # Final meaningful verification
    assert not service_path.exists()
    res = subprocess.run(
        [sys.executable, str(mock_wrapper_path), "daemon", "status"],
        capture_output=True,
        text=True,
    )
    assert (
        f"{TEST_SERVICE_NAME}.service could not be found" in res.stdout
        or res.returncode != 0
    )
