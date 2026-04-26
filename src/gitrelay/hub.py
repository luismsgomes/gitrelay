# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import logging
import shutil
import subprocess
from pathlib import Path

from .config import MainConfig

logger = logging.getLogger(__name__)


def init_hub(name: str) -> Path:
    """
    Initializes a new local bare git repository (hub).

    Args:
        name: The name of the hub.

    Returns:
        The Path to the newly created hub.

    Raises:
        FileNotFoundError: If the main configuration is not found.
        FileExistsError: If the hub directory already exists.
        subprocess.CalledProcessError: If the 'git init' command fails.
    """
    config = MainConfig.load()
    hub_dir = config.local_hubs_dir.expanduser()
    hub_path = hub_dir / f"{name}.git"

    if hub_path.exists():
        raise FileExistsError(f"Hub already exists at {hub_path}")

    hub_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", str(hub_path)], check=True)

    logger.info("Successfully initialized hub: %s at %s", name, hub_path)
    return hub_path


def delete_hub(name: str) -> Path:
    """
    Deletes a local bare git repository (hub) and its associated sync logs.

    Args:
        name: The name of the hub.

    Returns:
        The Path to the deleted hub.

    Raises:
        FileNotFoundError: If the main configuration or the hub itself is not found.
    """
    config = MainConfig.load()
    hub_dir = config.local_hubs_dir.expanduser()
    hub_path = hub_dir / f"{name}.git"

    if not hub_path.exists():
        raise FileNotFoundError(f"Hub '{name}' not found at {hub_path}")

    # 1. Remove the repository directory
    shutil.rmtree(hub_path)

    # 2. Remove associated sync logs if they exist
    log_dir = Path("~/.cache/gitrelay/logs/sync").expanduser() / name
    if log_dir.exists():
        shutil.rmtree(log_dir)

    logger.info("Successfully deleted hub: %s", name)
    return hub_path
