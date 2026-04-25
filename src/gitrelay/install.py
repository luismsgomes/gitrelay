# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICE_NAME = "gitrelay"

SERVICE_TEMPLATE = """[Unit]
Description=Git Relay background synchronization daemon
After=network.target

[Service]
Type=simple
ExecStart="{executable}" daemon start
Restart=always
RestartSec=10
Environment=PATH={path}

[Install]
WantedBy=default.target
"""


def get_executable_path() -> str:
    """Returns the absolute path to the current gitrelay executable."""
    executable = subprocess.run(
        ["which", "gitrelay"], capture_output=True, text=True
    ).stdout.strip()

    if not executable:
        # Fallback to absolute path of the script if which fails
        executable = str(Path(sys.prefix) / "bin" / "gitrelay")
        if not Path(executable).exists():
            executable = str(Path(sys.argv[0]).absolute())

    return executable


def install_cli_symlink() -> bool:
    """Creates ~/.local/bin/gitrelay symlink pointing to the current executable."""
    target = Path("~/.local/bin/gitrelay").expanduser()
    current_exe = Path(get_executable_path())

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(current_exe)
        logger.info("Successfully created symlink: %s -> %s", target, current_exe)
        return True
    except Exception as e:
        logger.error("Error creating symlink: %s", e)
        return False


def check_cli_symlink() -> bool:
    """Checks if the CLI symlink is correctly installed."""
    target = Path("~/.local/bin/gitrelay").expanduser()
    if not (target.exists() or target.is_symlink()):
        return False

    current_exe = get_executable_path()
    return os.path.realpath(target) == str(current_exe)


def uninstall_cli_symlink() -> bool:
    """Removes ~/.local/bin/gitrelay symlink."""
    target = Path("~/.local/bin/gitrelay").expanduser()
    try:
        if target.exists() or target.is_symlink():
            target.unlink()
            logger.info("Removed symlink: %s", target)
            return True
        else:
            logger.warning("Symlink not found: %s", target)
            return False
    except Exception as e:
        logger.error("Error removing symlink: %s", e)
        return False


def install_systemd_service() -> bool:
    """Installs and enables the systemd user service."""
    user_config_dir = Path("~/.config/systemd/user").expanduser()
    user_config_dir.mkdir(parents=True, exist_ok=True)

    service_file = user_config_dir / f"{SERVICE_NAME}.service"
    executable = get_executable_path()
    path_env = os.environ.get("PATH", "")

    try:
        # Systemd unit files handle quotes for paths with spaces
        service_file.write_text(
            SERVICE_TEMPLATE.format(executable=executable, path=path_env)
        )
        if not shutil.which("systemctl"):
            logger.error(
                "Error: 'systemctl' command not found. Systemd service cannot be managed."
            )
            return False
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", f"{SERVICE_NAME}.service"],
            check=True,
        )
        logger.info(
            "Successfully installed and started systemd service: %s", SERVICE_NAME
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        logger.error("Error installing systemd service: %s", e)
        return False


def uninstall_systemd_service() -> bool:
    """Disables and removes the systemd user service."""
    user_config_dir = Path("~/.config/systemd/user").expanduser()
    service_file = user_config_dir / f"{SERVICE_NAME}.service"

    try:
        if shutil.which("systemctl"):
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", f"{SERVICE_NAME}.service"],
                check=False,
            )
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        if service_file.exists():
            service_file.unlink()
            logger.info("Removed systemd service file: %s", service_file)
            return True
        else:
            logger.warning("Systemd service file not found: %s", service_file)
            return False
    except Exception as e:
        logger.error("Error uninstalling systemd service: %s", e)
        return False


def is_systemd_service_installed() -> bool:
    """Checks if the systemd user service is installed."""
    user_config_dir = Path("~/.config/systemd/user").expanduser()
    return (user_config_dir / f"{SERVICE_NAME}.service").exists()
