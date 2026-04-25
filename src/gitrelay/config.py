import json
from enum import Enum
from pathlib import Path
from typing import Self
import fcntl
from pydantic import BaseModel, Field


class SyncDirection(str, Enum):
    FETCH = "FETCH"
    PUSH = "PUSH"
    BOTH = "BOTH"


class BaseConfigFile(BaseModel):
    """
    Base class for configuration files with JSON persistence and concurrency safety.

    This class provides a thread-safe and process-safe way to load and save
    Pydantic models as JSON files. It uses `fcntl` for advisory file locking
    to ensure consistency across multiple processes.
    """

    @classmethod
    def get_config_path(cls) -> Path:
        """Return the target Path for this configuration file."""
        raise NotImplementedError("Subclasses must implement get_config_path")

    @classmethod
    def load(cls) -> Self:
        """
        Load the configuration from disk with a shared (read) lock.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            pydantic.ValidationError: If the data does not match the model schema.
        """
        path = cls.get_config_path().expanduser()

        with open(path, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
                return cls.model_validate(data)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def save(self) -> None:
        """
        Save the configuration to disk with an exclusive (write) lock.

        Files are saved as indented JSON for human readability.
        """
        path = self.get_config_path().expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                f.truncate()
                # Use model_dump(mode="json") to handle non-serializable types like Path
                data = self.model_dump(mode="json")
                json.dump(data, f, indent=4)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


class MainConfig(BaseConfigFile):
    sync_enabled: bool = Field(
        default=True,
        description="Whether the background synchronization is enabled.",
    )
    scan_enabled: bool = Field(
        default=True,
        description="Whether automatic hub scanning is enabled.",
    )
    local_hubs_dir: Path = Field(
        default=Path("~/githubs"),
        description="Directory where local hubs are stored.",
    )
    local_repos_dirs: list[Path] = Field(
        default_factory=lambda: [Path("~")],
        description="List of directories to scan for local repositories.",
    )
    default_local_repo_sync_interval_secs: int = Field(
        default=3600,
        description="Default synchronization interval for local repositories in seconds.",
    )
    default_remote_hub_sync_interval_secs: int = Field(
        default=3600,
        description="Default synchronization interval for remote hubs in seconds.",
    )
    default_ajust_sync_interval: bool = Field(
        default=True,
        description="Whether to automatically adjust sync intervals based on activity.",
    )
    default_local_bare_repo_sync_direction: SyncDirection = Field(
        default=SyncDirection.FETCH,
        description="Default sync direction for local bare repositories.",
    )
    default_remote_hub_sync_direction: SyncDirection = Field(
        default=SyncDirection.BOTH,
        description="Default sync direction for remote hubs.",
    )

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/tool.json")


class SyncBaseConfig(BaseModel):
    sync_interval_secs: int = Field(
        description="Interval between synchronization runs in seconds."
    )
    sync_interval_adjust: bool = Field(
        description="Whether to dynamically adjust the synchronization interval based on activity."
    )


class LocalRepoSyncBaseConfig(BaseModel):
    local_repo_path: Path = Field(
        description="Filesystem path to the local repository."
    )
    local_repo_alias: str = Field(
        description="The git remote name that will be added to the hub to refer to the repository."
    )
    local_hub_alias: str = Field(
        description="The git remote name that will be added to the repository to refer to the hub."
    )


class LocalRepoSyncConfig(LocalRepoSyncBaseConfig):
    @property
    def sync_direction(self) -> SyncDirection:
        # cannot push to normal (non-bare) repos
        return SyncDirection.FETCH


class LocalBareRepoSyncConfig(LocalRepoSyncBaseConfig):
    sync_direction: SyncDirection = Field(
        description="Synchronization direction for local bare repositories."
    )


class RemoteHostConfig(BaseModel):
    remote_host_name: str = Field(
        description="Name of the remote host as defined in SSH configuration."
    )
    remote_hubs_dir: Path = Field(
        description="Base directory for hubs on the remote host."
    )
    remote_hub_scan_interval_secs: int = Field(
        description="Interval between scans for new hubs on the remote host."
    )
    remote_hub_scan_enabled: bool = Field(
        description="Whether automatic hub scanning is enabled for this host."
    )


class RemoteHubSyncBaseConfig(SyncBaseConfig):
    remote_hub_name: Path = Field(description="Name of the remote hub.")
    remote_host_config: RemoteHostConfig = Field(
        description="Configuration for the remote host."
    )
    remote_hub_alias: str = Field(
        description="The git remote name that will be added to the local hub to refer to the remote hub."
    )


class RemoteHubSyncConfig(RemoteHubSyncBaseConfig):
    pass


class LocalHubConfig(BaseModel):
    hub_name: str = Field(description="Name of the local hub.")
    synced_local_repos: list[LocalRepoSyncConfig] = Field(
        description="List of local non-bare repositories synchronized with this hub."
    )
    synced_local_bare_repos: list[LocalBareRepoSyncConfig] = Field(
        description="List of local bare repositories synchronized with this hub."
    )
    synced_remote_hubs: list[RemoteHubSyncConfig] = Field(
        description="List of remote hubs synchronized with this hub."
    )


class LocalHubsConfig(BaseConfigFile):
    local_hubs: list[LocalHubConfig] = Field(
        description="List of all local hubs managed by gitrelay."
    )

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/local-hubs.json")


class HostsConfig(BaseConfigFile):
    remote_hosts: list[RemoteHostConfig] = Field(
        description="List of all configured remote hosts for synchronization."
    )

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/remote-hosts.json")
