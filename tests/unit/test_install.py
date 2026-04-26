import os
from unittest.mock import MagicMock, patch

import pytest

from gitrelay.main import (
    check_cli_symlink,
    get_executable_path,
    install_cli_symlink,
    uninstall_cli_symlink,
)


@pytest.fixture(autouse=True)
def set_default_service_name(monkeypatch):
    """Ensures a predictable service name for all tests."""
    monkeypatch.setenv("GITRELAY_SERVICE_NAME", "gitrelay")


@pytest.fixture
def mock_home(tmp_path):
    """Mocks the user's home directory structure for installation tests."""
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    return tmp_path


def test_get_executable_path_via_which():
    """Verifies get_executable_path returns path from 'which'."""
    with patch("gitrelay.main.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="/usr/local/bin/gitrelay")
        assert get_executable_path() == "/usr/local/bin/gitrelay"


def test_install_cli_symlink(mock_home):
    """Verifies symlink creation and idempotency."""
    exe_path = "/tmp/actual_exe"
    target_link = mock_home / ".local" / "bin" / "gitrelay"

    with (
        patch("gitrelay.main.get_executable_path", return_value=exe_path),
        patch("gitrelay.main.Path.expanduser", return_value=target_link),
    ):
        # 1. First install
        assert install_cli_symlink() is True
        assert target_link.is_symlink()
        assert os.path.realpath(target_link) == exe_path

        # 2. Check symlink
        assert check_cli_symlink() is True

        # 3. Idempotency check (already exists)
        assert install_cli_symlink() is True
        assert target_link.is_symlink()


def test_uninstall_cli_symlink(mock_home):
    """Verifies symlink removal."""
    target_link = mock_home / ".local" / "bin" / "gitrelay"
    target_link.symlink_to("/dev/null")

    with patch("gitrelay.main.Path.expanduser", return_value=target_link):
        assert uninstall_cli_symlink() is True
        assert not target_link.exists()
