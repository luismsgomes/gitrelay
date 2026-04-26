# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Default service name
SERVICE_NAME = "gitrelay"

SERVICE_TEMPLATE = """[Unit]
Description=Git Relay background synchronization daemon
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=10
Environment=PATH={path}

[Install]
WantedBy=default.target
"""


def get_service_name() -> str:
    """Returns the currently active service name (can be overridden by environment)."""
    return os.environ.get("GITRELAY_SERVICE_NAME", SERVICE_NAME)


def run_systemctl(
    command: str,
    args: Optional[List[str]] = None,
    check: bool = True,
    merge_stderr: bool = False,
) -> subprocess.CompletedProcess:
    """Invokes systemctl for the current user service."""
    if not shutil.which("systemctl"):
        raise RuntimeError("systemctl command not found.")

    if args is None:
        args = []

    service_file = f"{get_service_name()}.service"
    cmd = ["systemctl", "--user", command] + args + [service_file]

    stderr = subprocess.STDOUT if merge_stderr else subprocess.PIPE
    return subprocess.run(
        cmd,
        capture_output=False,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        check=check,
    )


def start_service():
    """Starts the systemd user service."""
    run_systemctl("start")


def stop_service():
    """Stops the systemd user service."""
    run_systemctl("stop")


def restart_service():
    """Restarts the systemd user service."""
    run_systemctl("restart")


def enable_service(now: bool = True):
    """Enables the systemd user service."""
    args = ["--now"] if now else []
    run_systemctl("enable", args=args)


def disable_service(now: bool = True):
    """Disables the systemd user service."""
    args = ["--now"] if now else []
    run_systemctl("disable", args=args)


def get_service_status() -> str:
    """Returns the output of systemctl status."""
    # We use check=False because systemctl status returns non-zero
    # if the service is not running or is not found.
    # We merge stderr to capture "could not be found" messages.
    result = run_systemctl("status", check=False, merge_stderr=True)
    return result.stdout


def is_service_active() -> bool:
    """Checks if the service is currently active (running)."""
    result = run_systemctl("is-active", check=False)
    return result.stdout.strip() == "active"


def daemon_reload():
    """Performs systemctl daemon-reload."""
    if not shutil.which("systemctl"):
        return
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)


def install_service(dry_run: bool = False):
    """Installs and enables the systemd user service."""
    from .main import get_executable_path

    user_config_dir = Path("~/.config/systemd/user").expanduser()
    user_config_dir.mkdir(parents=True, exist_ok=True)

    service_name = get_service_name()
    service_file = user_config_dir / f"{service_name}.service"

    executable = get_executable_path()
    # Pattern: "/path/to/bin/gitrelay" daemon run [--dry-run]
    exec_start = f'"{executable}" daemon run'
    if dry_run:
        exec_start += " --dry-run"

    path_env = os.environ.get("PATH", "")

    try:
        service_file.write_text(
            SERVICE_TEMPLATE.format(exec_start=exec_start, path=path_env)
        )
        daemon_reload()
        enable_service(now=True)
        logger.info("Installed and started systemd service: %s", service_name)
        return True
    except Exception as e:
        logger.error("Error installing systemd service: %s", e)
        return False


def uninstall_service():
    """Disables and removes the systemd user service."""
    user_config_dir = Path("~/.config/systemd/user").expanduser()
    service_name = get_service_name()
    service_file = user_config_dir / f"{service_name}.service"

    try:
        disable_service(now=True)
        daemon_reload()
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


def is_service_installed() -> bool:
    """Checks if the systemd user service is installed."""
    user_config_dir = Path("~/.config/systemd/user").expanduser()
    service_name = get_service_name()
    return (user_config_dir / f"{service_name}.service").exists()
