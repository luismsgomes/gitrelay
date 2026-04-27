# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

from abc import ABC, abstractmethod
from .config import MainConfig

class BaseJob(ABC):
    """Abstract base class for all background jobs."""

    @abstractmethod
    def secs_until_next_run(self, main_config: MainConfig) -> int:
        """Returns the number of seconds until the job's next scheduled run."""
        pass

    @abstractmethod
    def run(self) -> None:
        """Executes the job logic."""
        pass
