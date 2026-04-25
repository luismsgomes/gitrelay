# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

from abc import ABC, abstractmethod


class BaseJob(ABC):
    """Abstract base class for all background jobs."""

    @abstractmethod
    def secs_until_next_run(self) -> int:
        """Returns the number of seconds until the job's next scheduled run."""
        pass

    @abstractmethod
    def run(self) -> None:
        """Executes the job logic."""
        pass
