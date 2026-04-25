# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import logging
from typing import List
from .job import BaseJob

logger = logging.getLogger(__name__)


class SyncJob(BaseJob):
    """Synchronization job implementation."""

    def secs_until_next_run(self) -> int:
        """Returns the number of seconds until the job's next scheduled run."""
        return 3600

    def run(self) -> None:
        """Executes the synchronization logic."""
        logger.info("Running sync job... REVIEW")


def get_sync_jobs() -> List[SyncJob]:
    """Returns a list of all active synchronization jobs."""
    return []
