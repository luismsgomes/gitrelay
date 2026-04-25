# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import logging
from typing import List
from .job import BaseJob

logger = logging.getLogger(__name__)


class ScanJob(BaseJob):
    """Scanning job implementation."""

    def secs_until_next_run(self) -> int:
        """Returns the number of seconds until the job's next scheduled run."""
        return 3600

    def run(self) -> None:
        """Executes the scanning logic."""
        logger.info("Running scan job... REVIEW")


def get_scan_jobs() -> List[ScanJob]:
    """Returns a list of all active scanning jobs."""
    return []
