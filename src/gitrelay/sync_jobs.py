# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import logging
import os
import time
from abc import abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Generic, List, Optional, Self, TypeVar

from pydantic import BaseModel, Field

from .config import (
    LocalBareRepoSyncConfig,
    LocalHubConfig,
    LocalHubsConfig,
    LocalRepoSyncConfig,
    RemoteHubSyncConfig,
    SyncBaseConfig,
)
from .job import BaseJob

logger = logging.getLogger(__name__)


class CommitInfo(BaseModel):
    """Information about a specific git commit."""

    hash: str = Field(description="The full SHA-1 hash of the commit.")
    timestamp: datetime = Field(
        description="Commit datetime. Used to dynamically adjust sync frequency."
    )


class SyncResult(BaseModel):
    """The result of a single synchronization run, stored as a 'datum' in JSONL logs."""

    timestamp: datetime = Field(
        default_factory=datetime.now, description="The datetime when the sync started."
    )
    commits_fetched: List[CommitInfo] = Field(
        default_factory=list,
        description="List of commits successfully fetched from the target.",
    )
    commits_pushed: List[CommitInfo] = Field(
        default_factory=list,
        description="List of commits successfully pushed to the target.",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of error messages. An empty list signifies a successful run.",
    )

    @property
    def success(self) -> bool:
        """Returns True if no errors occurred during the sync."""
        return len(self.errors) == 0

    @classmethod
    def load_last(cls, path: Path) -> Optional[Self]:
        """
        Efficiently loads the most recent result from the end of a JSONL log file.
        Returns None if the file is missing, empty, or malformed.
        """
        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                try:
                    # Seek to the end, then move back to find the last newline
                    f.seek(-2, os.SEEK_END)
                    while f.read(1) != b"\n":
                        f.seek(-2, os.SEEK_CUR)
                except (OSError, ValueError):
                    # File is too small or has no newlines, read from start
                    f.seek(0)

                last_line = f.readline().decode("utf-8")
                if not last_line.strip():
                    return None
                return cls.model_validate_json(last_line)
        except Exception as e:
            logger.warning("Could not load last sync result from %s: %s", path, e)
            return None

    def append_to_log(self, path: Path) -> None:
        """Appends the result as a single JSON line to the specified file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as f:
                f.write(self.model_dump_json() + "\n")
        except Exception as e:
            logger.error("Failed to record sync result to %s: %s", path, e)


# Define a TypeVar that is bound to SyncBaseConfig
T = TypeVar("T", bound=SyncBaseConfig)


class SyncJob(BaseJob, Generic[T]):
    """Abstract base class for synchronization jobs with automated result logging."""

    def __init__(
        self,
        local_hub_config: LocalHubConfig,
        sync_target_config: T,
    ):
        self.local_hub_config = local_hub_config
        self.sync_target_config = sync_target_config
        self.last_result: Optional[SyncResult] = SyncResult.load_last(self.log_path)

    @property
    def log_path(self) -> Path:
        """Returns the path to the JSONL log file for this specific sync job."""
        base_log_dir = Path("~/.cache/gitrelay/logs/sync").expanduser()
        hub_path = base_log_dir / self.local_hub_config.hub_name
        return hub_path / f"{self.sync_target_config.target_alias}.jsonl"

    def secs_until_next_run(self) -> int:
        """Returns the number of seconds until the next scheduled run."""
        now = time.time()
        # Use 0.0 timestamp if never run to ensure it is overdue
        last_ts = self.last_result.timestamp.timestamp() if self.last_result else 0.0
        elapsed_secs = int(now - last_ts)
        return max(0, self.sync_target_config.sync_interval_secs - elapsed_secs)

    def run(self) -> None:
        """Executes the synchronization logic and logs the result."""
        result = SyncResult()
        try:
            self._run(result)
        except Exception as e:
            result.errors.append(str(e))
            logger.error("Sync job crashed: %s", e)
        finally:
            result.append_to_log(self.log_path)
            self.last_result = result

    @abstractmethod
    def _run(self, result: SyncResult) -> None:
        """Actual synchronization implementation to be provided by subclasses."""
        pass


class LocalRepoSyncJob(SyncJob[LocalRepoSyncConfig]):
    """Synchronization job between a local hub and a local non-bare repository."""

    def _run(self, result: SyncResult) -> None:
        logger.info(
            "Syncing local hub %s with local repo %s (alias: %s)",
            self.local_hub_config.hub_name,
            self.sync_target_config.local_repo_path,
            self.sync_target_config.target_alias,
        )


class LocalBareRepoSyncJob(SyncJob[LocalBareRepoSyncConfig]):
    """Synchronization job between a local hub and a local bare repository."""

    def _run(self, result: SyncResult) -> None:
        logger.info(
            "Syncing local hub %s with local bare repo %s (alias: %s, direction: %s)",
            self.local_hub_config.hub_name,
            self.sync_target_config.local_repo_path,
            self.sync_target_config.target_alias,
            self.sync_target_config.sync_direction,
        )


class RemoteHubSyncJob(SyncJob[RemoteHubSyncConfig]):
    """Synchronization job between a local hub and a remote hub."""

    def _run(self, result: SyncResult) -> None:
        logger.info(
            "Syncing local hub %s with remote hub %s (host: %s, alias: %s)",
            self.local_hub_config.hub_name,
            self.sync_target_config.remote_hub_name,
            self.sync_target_config.remote_host_config.remote_host_name,
            self.sync_target_config.target_alias,
        )


def get_sync_jobs() -> List[SyncJob]:
    """Returns a list of all active synchronization jobs from configuration."""
    try:
        hubs_config = LocalHubsConfig.load()
    except FileNotFoundError:
        return []

    jobs: List[SyncJob] = []
    for hub in hubs_config.local_hubs:
        for repo_config in hub.synced_local_repos:
            jobs.append(
                LocalRepoSyncJob(local_hub_config=hub, sync_target_config=repo_config)
            )

        for bare_repo_config in hub.synced_local_bare_repos:
            jobs.append(
                LocalBareRepoSyncJob(
                    local_hub_config=hub, sync_target_config=bare_repo_config
                )
            )

        for remote_hub_config in hub.synced_remote_hubs:
            jobs.append(
                RemoteHubSyncJob(
                    local_hub_config=hub, sync_target_config=remote_hub_config
                )
            )

    return jobs
