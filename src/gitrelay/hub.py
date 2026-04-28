# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple

from .config import (
    LocalHubConfig,
    LocalHubsConfig,
    MainConfig,
    RepositoryConfig,
    SyncDirection,
)
from .git import (
    generate_repo_id,
    git_get_repo_id,
    git_set_repo_id,
    init_repository,
    is_bare_repository,
)

logger = logging.getLogger(__name__)


def init_hub(hub_name: str) -> Tuple[Path, bool]:
    """
    Initializes a new hub and registers it in config.

    Args:
        hub_name: The name of the hub.

    Returns:
        A tuple of (Path to the hub, already_existed_on_disk bool).

    Raises:
        FileNotFoundError: If the main configuration is not found.
        FileExistsError: If the hub is already registered in configuration.
        subprocess.CalledProcessError: If the 'git init' command fails.
    """
    # 1. Check configuration
    hubs_config = LocalHubsConfig.load()
    if any(h.hub_name == hub_name for h in hubs_config.local_hubs):
        raise FileExistsError(
            f"Hub '{hub_name}' is already registered in configuration."
        )

    config = MainConfig.load()
    hub_dir = config.local_hubs_dir.expanduser()
    hub_path = hub_dir / f"{hub_name}.git"

    already_existed = hub_path.exists()
    if not already_existed:
        # 2. Initialize the physical repository
        init_repository(hub_path)

    # 3. Register in configuration
    hubs_config.local_hubs.append(LocalHubConfig(hub_name=hub_name))
    hubs_config.save()

    if already_existed:
        logger.info("Registered existing hub: %s at %s", hub_name, hub_path)
    else:
        logger.info("Successfully initialized hub: %s at %s", hub_name, hub_path)

    return hub_path, already_existed


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
    # 1. Remove from configuration
    hubs_config = LocalHubsConfig.load()
    original_count = len(hubs_config.local_hubs)
    hubs_config.local_hubs = [
        h for h in hubs_config.local_hubs if h.hub_name != hub_name
    ]

    if len(hubs_config.local_hubs) == original_count:
        logger.warning("Hub '%s' was not found in configuration.", hub_name)
    else:
        hubs_config.save()

    # 2. Determine paths
    config = MainConfig.load()
    hub_dir = config.local_hubs_dir.expanduser()
    hub_path = hub_dir / f"{hub_name}.git"

    if not hub_path.exists():
        raise FileNotFoundError(f"Hub '{hub_name}' not found at {hub_path}")

    # 3. Remove the repository directory
    shutil.rmtree(hub_path)

    # 4. Remove associated sync logs if they exist
    log_dir = Path("~/.cache/gitrelay/logs/sync").expanduser() / hub_name
    if log_dir.exists():
        shutil.rmtree(log_dir)

    logger.info("Successfully deleted hub: %s", hub_name)
    return hub_path


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

    # 1. Ensure the repository has a unique ID
    repo_id = git_get_repo_id(repo_path)
    if not repo_id:
        repo_id = generate_repo_id()
        git_set_repo_id(repo_path, repo_id)

    is_bare = is_bare_repository(repo_path)

    if not is_bare:
        # Regular repo: ONLY FETCH is allowed
        if direction and direction != SyncDirection.FETCH:
            raise ValueError(
                "Regular (non-bare) repositories only support 'fetch' direction."
            )
        dir_val = SyncDirection.FETCH
    else:
        # Bare repo: use BOTH by default if not specified
        dir_val = direction or SyncDirection.BOTH

    # 2. Create and save individual repository configuration
    repo_config = RepositoryConfig(
        repo_id=repo_id,
        hub_name=hub_name,
        local_repo_path=repo_path,
        is_bare=is_bare,
        sync_interval_secs=interval_secs,
        sync_interval_adjust=adjust_interval,
        sync_direction=dir_val,
    )
    repo_config.save()

    # 3. Register the repo ID in the hub configuration
    hub_config.add_synced_local_repo_id(repo_id)
    hubs_config.save()

    logger.info("Setup sync for repo %s with hub %s", repo_path, hub_name)
