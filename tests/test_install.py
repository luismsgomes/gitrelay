import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gitrelay.install import (
    check_cli_symlink,
    get_executable_path,
    install_cli_symlink,
    install_systemd_service,
    uninstall_cli_symlink,
    uninstall_systemd_service,
)


@pytest.fixture
def mock_home(tmp_path):
    """Mocks the user's home directory structure for installation tests."""
    local_bin = tmp_path / ".local" / "bin"
    systemd_user = tmp_path / ".config" / "systemd" / "user"
    local_bin.mkdir(parents=True)
    systemd_user.mkdir(parents=True)
    return tmp_path


def test_get_executable_path_via_which():
    """Verifies get_executable_path returns path from 'which'."""
    with patch("gitrelay.install.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="/usr/local/bin/gitrelay")
        assert get_executable_path() == "/usr/local/bin/gitrelay"


def test_install_cli_symlink(mock_home):
    """Verifies symlink creation and idempotency."""
    exe_path = "/tmp/actual_exe"
    target_link = mock_home / ".local" / "bin" / "gitrelay"

    with (
        patch("gitrelay.install.get_executable_path", return_value=exe_path),
        patch("gitrelay.install.Path.expanduser", return_value=target_link),
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

    with patch("gitrelay.install.Path.expanduser", return_value=target_link):
        assert uninstall_cli_symlink() is True
        assert not target_link.exists()


def test_install_systemd_service_logic(mock_home):
    """Verifies systemd unit creation and command execution."""
    config_dir = mock_home / ".config" / "systemd" / "user"
    exe_path = "/usr/bin/gitrelay"

    with (
        patch("gitrelay.install.get_executable_path", return_value=exe_path),
        patch("gitrelay.install.Path.expanduser", return_value=config_dir),
        patch("gitrelay.install.shutil.which", return_value="systemctl"),
        patch("gitrelay.install.subprocess.run") as mock_run,
    ):

        mock_run.return_value = MagicMock(returncode=0)

        assert install_systemd_service() is True

        service_file = config_dir / "gitrelay.service"
        assert service_file.exists()
        content = service_file.read_text()
        assert f'ExecStart="{exe_path}" daemon start' in content

        # Check command sequence
        assert mock_run.call_count == 2
        # First call: daemon-reload
        assert "daemon-reload" in mock_run.call_args_list[0][0][0]
        # Second call: enable --now
        assert "enable" in mock_run.call_args_list[1][0][0]


def test_install_systemd_service_with_spaces(tmp_path):
    """
    Verifies that the executable path has spaces and is quoted in the systemd unit,
    and validates the syntax using systemd-analyze if available.
    (Moved from test_paths_with_spaces)
    """
    config_dir = tmp_path / "systemd" / "user"
    config_dir.mkdir(parents=True)

    # Create a dummy executable at a path with spaces to satisfy systemd-analyze
    bin_dir = tmp_path / "My Tools" / "bin"
    bin_dir.mkdir(parents=True)
    bad_exe = bin_dir / "gitrelay"
    bad_exe.touch(mode=0o755)
    bad_exe_str = str(bad_exe)

    # Use the real shutil.which here, outside of any patches
    analyze_tool = shutil.which("systemd-analyze")

    with (
        patch("gitrelay.install.get_executable_path") as mock_get_exe,
        patch("gitrelay.install.Path") as mock_path,
    ):

        mock_get_exe.return_value = bad_exe_str
        mock_path_obj = MagicMock(spec=Path)
        mock_path_obj.expanduser.return_value = config_dir
        mock_path.side_effect = lambda p: (
            mock_path_obj if p == "~/.config/systemd/user" else Path(p)
        )

        with (
            patch("gitrelay.install.shutil.which") as mock_which,
            patch("gitrelay.install.subprocess.run") as mock_run,
        ):

            mock_which.return_value = "systemctl"
            mock_run.return_value = MagicMock(returncode=0)

            install_systemd_service()

            service_file = config_dir / "gitrelay.service"
            content = service_file.read_text()

            assert f'ExecStart="{bad_exe_str}" daemon start' in content

            if analyze_tool:
                res = subprocess.run(
                    [analyze_tool, "verify", str(service_file)],
                    capture_output=True,
                    text=True,
                )
                assert (
                    res.returncode == 0
                ), f"Systemd syntax validation failed: {res.stderr}"
            else:
                pytest.skip(
                    "systemd-analyze not found, skipping unit syntax validation."
                )


def test_uninstall_systemd_service(mock_home):
    """Verifies service cleanup."""
    config_dir = mock_home / ".config" / "systemd" / "user"
    service_file = config_dir / "gitrelay.service"
    service_file.touch()

    with (
        patch("gitrelay.install.Path.expanduser", return_value=config_dir),
        patch("gitrelay.install.shutil.which", return_value="systemctl"),
        patch("gitrelay.install.subprocess.run") as mock_run,
    ):

        mock_run.return_value = MagicMock(returncode=0)

        assert uninstall_systemd_service() is True
        assert not service_file.exists()
        # Verify disable was called
        assert "disable" in mock_run.call_args_list[0][0][0]
