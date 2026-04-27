import fcntl
import json
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Optional, Self, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    # We use a PrivateAttr-like pattern (Pydantic handles this automatically for
    # attributes starting with _) to track when we last read the file.
    _last_loaded_at: float = 0.0

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
                obj = cls.model_validate(data)
                # Store the modification time of the file we just read
                obj._last_loaded_at = path.stat().st_mtime
                return obj
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def reload(self) -> bool:
        """
        Reload the configuration from disk if the file has been modified.

        Returns:
            bool: True if the configuration was actually reloaded, False otherwise.
        """
        path = self.get_config_path().expanduser()
        if not path.exists():
            return False

        current_mtime = path.stat().st_mtime
        if current_mtime <= self._last_loaded_at:
            return False

        # File was modified, perform a fresh load
        new_data = self.load()
        # Update our own state from the new object
        # Note: model_dump(exclude_unset=True) could be used for partial updates,
        # but here we want a full state refresh.
        for key, value in new_data.model_dump().items():
            setattr(self, key, value)
        self._last_loaded_at = current_mtime
        return True

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
                # Trigger full validation before saving
                self.model_validate(self.model_dump())

                f.seek(0)
                f.truncate()
                # Use model_dump(mode="json") to handle non-serializable types like Path
                data = self.model_dump(mode="json")
                json.dump(data, f, indent=4)
                # Update timestamp after saving to avoid immediate reload
                self._last_loaded_at = path.stat().st_mtime
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


class MainConfig(BaseConfigFile):
    """
    Main configuration for the gitrelay tool.

    Contains global settings like enabling/disabling sync and scan jobs,
    default synchronization intervals, and directory locations.
    """

    sync_enabled: bool = Field(
        default=True,
        description="Whether the background synchronization is enabled.",
    )
    scan_enabled: bool = Field(
        default=True,
        description="Whether automatic hub scanning is enabled.",
    )
    local_hubs_dir: Path = Field(
        default_factory=lambda: Path("~/githubs"),
        description="Directory where local hubs are stored.",
    )
    local_repos_dirs: list[Path] = Field(
        default_factory=lambda: [Path("~")],
        description="List of directories to scan for local repositories.",
    )
    min_adjusted_sync_interval_secs: int = Field(
        default=60,
        description="Minimum synchronization interval after automatic adjustment (seconds).",
    )
    default_local_repo_sync_interval_secs: int = Field(
        default=3600,
        description="Default synchronization interval for local repos (seconds).",
    )
    default_local_bare_repo_sync_interval_secs: int = Field(
        default=3600,
        description="Default synchronization interval for local bare repos (seconds).",
    )
    default_remote_hub_sync_interval_secs: int = Field(
        default=3600,
        description="Default synchronization interval for remote hubs in seconds.",
    )
    default_adjust_sync_interval: bool = Field(
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
    idle_sleep_secs: int = Field(
        default=60,
        description="Time to sleep when no jobs are active.",
    )
    log_level: str = Field(
        default="WARNING",
        description="Logging level for the daemon (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )

    def setup_logging(self):
        """Configures or updates the global logging level based on configuration."""
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        # We use force=True to allow re-configuration if basicConfig was already called
        logging.basicConfig(
            level=level,
            format="%(levelname)s: %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
            force=True,
        )

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/main.json")


class SyncBaseConfig(BaseModel):
    """Base configuration for all synchronization targets."""

    sync_interval_secs: Optional[int] = Field(
        default=None, description="Interval between synchronization runs in seconds."
    )
    sync_interval_adjust: Optional[bool] = Field(
        default=None, description="Whether to adjust sync interval based on repository activity."
    )
    target_alias: str = Field(
        description="A name that will be used to refer to the sync target."
    )

    def get_sync_direction(self) -> SyncDirection:
        """Returns the synchronization direction for this target."""
        raise NotImplementedError("Subclasses must implement get_sync_direction")


class LocalRepoSyncBaseConfig(SyncBaseConfig):
    """Common configuration for all local synchronization targets."""

    local_repo_path: Path = Field(description="Path to the local repository.")


class LocalRepoSyncConfig(LocalRepoSyncBaseConfig):
    """Configuration for a local non-bare repository synchronization target."""

    def get_sync_direction(self) -> SyncDirection:
        "Synchronization direction for local repositories (always FETCH)."
        # cannot push to normal (non-bare) repos
        return SyncDirection.FETCH


class LocalBareRepoSyncConfig(LocalRepoSyncBaseConfig):
    """Configuration for a local bare repository synchronization target."""

    sync_direction: SyncDirection = Field(
        description="Synchronization direction for local bare repositories."
    )

    def get_sync_direction(self) -> SyncDirection:
        return self.sync_direction


class RemoteHostConfig(BaseModel):
    """Configuration for a remote host accessible via SSH."""

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


class RemoteHubSyncConfig(SyncBaseConfig):
    """Configuration for a remote hub synchronization target."""

    remote_hub_name: Path = Field(description="Name of the remote hub.")
    remote_host_config: RemoteHostConfig = Field(
        description="Configuration for the remote host."
    )
    sync_direction: SyncDirection = Field(
        default=SyncDirection.BOTH,
        description="Synchronization direction for remote hubs.",
    )

    def get_sync_direction(self) -> SyncDirection:
        return self.sync_direction


class LocalHubConfig(BaseModel):
    """Configuration for a local hub and its associated synchronization targets."""

    model_config = ConfigDict(validate_assignment=True)

    hub_name: str = Field(description="Name of the local hub.")
    synced_local_repos: list[LocalRepoSyncConfig] = Field(
        default_factory=list,
        description="List of local non-bare repositories synchronized with this hub.",
    )
    synced_local_bare_repos: list[LocalBareRepoSyncConfig] = Field(
        default_factory=list,
        description="List of local bare repositories synchronized with this hub.",
    )
    synced_remote_hubs: list[RemoteHubSyncConfig] = Field(
        default_factory=list,
        description="List of remote hubs synchronized with this hub.",
    )

    @property
    def all_sync_targets(self) -> Sequence[SyncBaseConfig]:
        """Returns a combined sequence of all synchronization targets."""
        return (
            list(self.synced_local_repos)
            + list(self.synced_local_bare_repos)
            + list(self.synced_remote_hubs)
        )

    @model_validator(mode="after")
    def validate_unique_aliases(self) -> Self:
        """Ensures that all target aliases within the hub are unique."""
        aliases = [t.target_alias for t in self.all_sync_targets]
        if len(aliases) != len(set(aliases)):
            duplicates = [a for a in set(aliases) if aliases.count(a) > 1]
            raise ValueError(f"Duplicate target aliases found: {', '.join(duplicates)}")
        return self

    def _check_alias_uniqueness(self, alias: str):
        if any(t.target_alias == alias for t in self.all_sync_targets):
            raise ValueError(
                f"Alias '{alias}' is already in use in hub '{self.hub_name}'"
            )

    def add_synced_local_repo(self, config: LocalRepoSyncConfig):
        """Adds a local repository to the hub with an immediate uniqueness check."""
        self._check_alias_uniqueness(config.target_alias)
        self.synced_local_repos.append(config)

    def add_synced_local_bare_repo(self, config: LocalBareRepoSyncConfig):
        """Adds a local bare repository with an immediate uniqueness check."""
        self._check_alias_uniqueness(config.target_alias)
        self.synced_local_bare_repos.append(config)

    def add_synced_remote_hub(self, config: RemoteHubSyncConfig):
        """Adds a remote hub to the hub with an immediate uniqueness check."""
        self._check_alias_uniqueness(config.target_alias)
        self.synced_remote_hubs.append(config)


class LocalHubsConfig(BaseConfigFile):
    """Configuration file containing all local hubs managed by gitrelay."""

    local_hubs: list[LocalHubConfig] = Field(
        default_factory=list,
        description="List of all local hubs managed by gitrelay.",
    )

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/local-hubs.json")


class HostsConfig(BaseConfigFile):
    """Configuration file containing all configured remote hosts."""

    remote_hosts: list[RemoteHostConfig] = Field(
        default_factory=list,
        description="List of all configured remote hosts for synchronization.",
    )

    @classmethod
    def get_config_path(cls) -> Path:
        return Path("~/.config/gitrelay/remote-hosts.json")
