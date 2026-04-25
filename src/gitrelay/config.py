import json
from enum import Enum
from pathlib import Path
from typing import Any, Self
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


class ToolConfig(BaseConfigFile):
    local_hubs_dir: Path = Path("~/githubs")

    local_repos_dirs: list[Path] = Field(default_factory=lambda: [Path("~")])

    default_local_repo_sync_interval_secs: int = 3600
    default_remote_hub_sync_interval_secs: int = 3600
    default_ajust_sync_interval: bool = True
    default_local_bare_repo_sync_direction: SyncDirection = SyncDirection.FETCH
    default_remote_hub_sync_direction: SyncDirection = SyncDirection.BOTH

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/tool.json")


class SyncBaseConfig(BaseModel):
    sync_interval_secs: int
    sync_interval_adjust: bool


class LocalRepoSyncBaseConfig(BaseModel):
    local_repo_path: Path
    local_repo_alias: str  # the git remote name that will be added to the hub to refer to the repo
    local_hub_alias: str   # the git remote name that will be added to the repo to refer to the hub


class LocalRepoSyncConfig(LocalRepoSyncBaseConfig):
    @property
    def sync_direction(self) -> SyncDirection:
        # cannot push to normal (non-bare) repos
        return SyncDirection.FETCH


class LocalBareRepoSyncConfig(LocalRepoSyncBaseConfig):
    sync_direction: SyncDirection


class RemoteHostConfig(BaseModel):
    remote_host_name: str
    remote_hubs_dir: Path
    remote_hub_scan_interval_secs: int
    remote_hub_scan_enabled: bool


class RemoteHubSyncBaseConfig(SyncBaseConfig):
    remote_hub_name: Path
    remote_host_config: RemoteHostConfig
    remote_hub_alias: str  # the git remote name that will be added to the local hub to refer to the remote hub


class RemoteHubSyncConfig(RemoteHubSyncBaseConfig):
    pass


class LocalHubConfig(BaseModel):
    hub_name: str
    synced_local_repos: list[LocalRepoSyncConfig]
    synced_local_bare_repos: list[LocalBareRepoSyncConfig]
    synced_remote_hubs: list[RemoteHubSyncConfig]


class LocalHubsConfig(BaseConfigFile):
    local_hubs: list[LocalHubConfig]

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/local-hubs.json")


class HostsConfig(BaseConfigFile):
    remote_hosts: list[RemoteHostConfig]

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/remote-hosts.json")
