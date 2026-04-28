from unittest.mock import MagicMock, patch

import pytest

from gitrelay.config import LocalHubConfig, MainConfig, SyncBaseConfig, SyncDirection
from gitrelay.daemon import daemon_start
from gitrelay.scan_jobs import ScanJob
from gitrelay.sync_jobs import SyncJob


class StopLoop(Exception):
    """
    Custom exception used to break the infinite 'while True' loop in the daemon.

    Now that the daemon has a global 'try/except' block, this exception will
    trigger a 'critical' log and a 'sys.exit(1)'.
    """

    pass


class MockSyncJob(SyncJob[SyncBaseConfig]):
    """A concrete implementation of the abstract SyncJob class for testing."""

    @property
    def target_alias(self) -> str:
        return self.sync_target_config.target_alias

    @property
    def sync_direction(self) -> SyncDirection:
        return SyncDirection.FETCH

    def _run(self, result) -> None:
        pass

    def get_default_sync_interval_secs(self, main_config: MainConfig) -> int:
        return 3600


@pytest.fixture
def mock_config():
    """A pytest fixture that creates a pre-configured mock of MainConfig."""
    config = MagicMock(spec=MainConfig)
    config.sync_enabled = True
    config.scan_enabled = True
    config.idle_sleep_secs = 10
    # By default, config.reload() returns False (no changes found on disk)
    config.reload.return_value = False
    return config


def test_daemon_loop_basic_execution(mock_config):
    """
    Verifies that the daemon:
    1. Fetches, sorts, and runs jobs.
    2. Correctly handles a 'crash' by logging it and exiting with code 1.
    """
    hub_config = MagicMock(spec=LocalHubConfig)
    hub_config.hub_name = "test-hub"

    job_config = MagicMock(spec=SyncBaseConfig)
    job_config.target_alias = "test-target"
    job_config.sync_interval_secs = 3600

    sync_job = MockSyncJob(local_hub_config=hub_config, sync_target_config=job_config)
    sync_job.secs_until_next_run = MagicMock(return_value=5)
    sync_job._run = MagicMock()

    scan_job = ScanJob()
    scan_job.secs_until_next_run = MagicMock(return_value=2)
    scan_job.run = MagicMock()

    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[sync_job]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[scan_job]),
        patch("gitrelay.daemon.time.sleep") as mock_sleep,
        patch("gitrelay.daemon.logger") as mock_logger,
    ):
        # ORCHESTRATION: Force exit on the 4th reload call
        mock_config.reload.side_effect = [False, False, False, StopLoop("Exit Loop")]

        # VERIFY SYSTEM EXIT: The daemon should now exit with code 1
        with pytest.raises(SystemExit) as excinfo:
            daemon_start()

        assert excinfo.value.code == 1

        # VERIFY LOGGING: Ensure the crash was logged with the StopLoop exception
        mock_logger.critical.assert_called_once()
        args, kwargs = mock_logger.critical.call_args
        assert "Daemon crashed" in args[0]
        assert isinstance(args[1], StopLoop)
        assert kwargs.get("exc_info") is True

        assert sync_job._run.called
        assert scan_job.run.called
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(5)


def test_daemon_loop_disabling_mid_cycle(mock_config):
    """
    Verifies the future-proof filtering logic:
    If sync_enabled becomes False, remaining SyncJobs should be skipped.
    """
    hub_config = MagicMock(spec=LocalHubConfig)
    hub_config.hub_name = "test-hub"

    job_config = MagicMock(spec=SyncBaseConfig)
    job_config.target_alias = "test-target1"
    job_config.sync_interval_secs = 3600

    job1 = MockSyncJob(local_hub_config=hub_config, sync_target_config=job_config)
    job1.secs_until_next_run = MagicMock(return_value=1)
    job1._run = MagicMock()

    job_config2 = MagicMock(spec=SyncBaseConfig)
    job_config2.target_alias = "test-target2"
    job_config2.sync_interval_secs = 3600

    job2 = MockSyncJob(local_hub_config=hub_config, sync_target_config=job_config2)
    job2.secs_until_next_run = MagicMock(return_value=2)
    job2._run = MagicMock()

    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[job1, job2]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[]),
        patch("gitrelay.daemon.time.sleep"),
        patch("gitrelay.daemon.logger"),
    ):

        def flip_config():
            mock_config.sync_enabled = False
            return True

        mock_config.reload.side_effect = [False, flip_config, StopLoop()]

        with pytest.raises(SystemExit):
            daemon_start()

        assert job1._run.called
        assert not job2._run.called


def test_daemon_idle_sleep_when_no_jobs(mock_config):
    """Verifies that daemon sleeps for idle_sleep_secs when no jobs are found."""
    mock_config.idle_sleep_secs = 42

    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[]),
        patch("gitrelay.daemon.time.sleep") as mock_sleep,
        patch("gitrelay.daemon.logger"),
    ):
        mock_config.reload.side_effect = [False, StopLoop()]

        with pytest.raises(SystemExit):
            daemon_start()

        mock_sleep.assert_called_once_with(42)
