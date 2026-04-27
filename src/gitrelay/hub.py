# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .config import (
    LocalBareRepoSyncConfig,
    LocalHubsConfig,
    LocalRepoSyncConfig,
    MainConfig,
    SyncDirection,
)

logger = logging.getLogger(__name__)


def init_hub(hub_name: str) -> Path:
    """
    Initializes a new hub.

    Args:
        hub_name: The name of the hub.

    Returns:
        The Path to the newly created hub.

    Raises:
        FileNotFoundError: If the main configuration is not found.
        FileExistsError: If the hub directory already exists.
        subprocess.CalledProcessError: If the 'git init' command fails.
    """
    config = MainConfig.load()
    hub_dir = config.local_hubs_dir.expanduser()
    hub_path = hub_dir / f"{hub_name}.git"

    if hub_path.exists():
        raise FileExistsError(f"Hub already exists at {hub_path}")

    hub_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", str(hub_path)], check=True)

    logger.info("Successfully initialized hub: %s at %s", hub_name, hub_path)
    return hub_path


def delete_hub(hub_name: str) -> Path:
    """
    Deletes a hub and its associated sync logs.

    Args:
        hub_name: The name of the hub.

    Returns:
        The Path to the deleted hub.

    Raises:
        FileNotFoundError: If the main configuration or the hub itself is not found.
    """
    config = MainConfig.load()
    hub_dir = config.local_hubs_dir.expanduser()
    hub_path = hub_dir / f"{hub_name}.git"

    if not hub_path.exists():
        raise FileNotFoundError(f"Hub '{hub_name}' not found at {hub_path}")

    # 1. Remove the repository directory
    shutil.rmtree(hub_path)

    # 2. Remove associated sync logs if they exist
    log_dir = Path("~/.cache/gitrelay/logs/sync").expanduser() / hub_name
    if log_dir.exists():
        shutil.rmtree(log_dir)

    logger.info("Successfully deleted hub: %s", hub_name)
    return hub_path


def is_bare_repository(path: Path) -> bool:
    """Checks if a directory is a bare git repository."""
    try:
        res = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-bare-repository"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip() == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def setup_sync_with_local_repo(
    hub_name: str,
    repo_path: Path,
    interval_secs: Optional[int] = None,
    adjust_interval: Optional[bool] = None,
    direction: Optional[SyncDirection] = None,
) -> None:
    """Setup synchronization between a local repository and a hub."""
    hubs_config = LocalHubsConfig.load()
    hub_config = next(
        (h for h in hubs_config.local_hubs if h.hub_name == hub_name), None
    )

    if not hub_config:
        raise ValueError(f"Hub '{hub_name}' not found in configuration.")

    repo_path = repo_path.absolute()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path not found: {repo_path}")

    # Unique alias based on folder name
    alias = repo_path.name

    if is_bare_repository(repo_path):
        # Bare repo: use BOTH by default if not specified
        dir_val = direction or SyncDirection.BOTH
        config = LocalBareRepoSyncConfig(
            target_alias=alias,
            local_repo_path=repo_path,
            sync_interval_secs=interval_secs,
            sync_interval_adjust=adjust_interval,
            sync_direction=dir_val,
        )
        hub_config.add_synced_local_bare_repo(config)
    else:
        # Regular repo: ONLY FETCH is allowed
        if direction and direction != SyncDirection.FETCH:
            raise ValueError(
                "Regular (non-bare) repositories only support 'fetch' direction."
            )
        config = LocalRepoSyncConfig(
            target_alias=alias,
            local_repo_path=repo_path,
            sync_interval_secs=interval_secs,
            sync_interval_adjust=adjust_interval,
        )
        hub_config.add_synced_local_repo(config)

    hubs_config.save()
    logger.info("Setup sync for repo %s with hub %s", repo_path, hub_name)
