import pytest
from unittest.mock import patch, MagicMock
from gitrelay.daemon import daemon_start
from gitrelay.config import MainConfig
from gitrelay.sync_jobs import SyncJob
from gitrelay.scan_jobs import ScanJob


class StopLoop(Exception):
    """Exception used to break the infinite daemon loop during testing."""

    pass


@pytest.fixture
def mock_config():
    config = MagicMock(spec=MainConfig)
    config.sync_enabled = True
    config.scan_enabled = True
    config.idle_sleep_secs = 10
    config.reload.return_value = False
    return config


def test_daemon_loop_basic_execution(mock_config):
    """Verifies that the daemon fetches, sorts, and runs jobs."""
    # We use real objects but mock the internal methods so isinstance() works
    sync_job = SyncJob()
    sync_job.secs_until_next_run = MagicMock(return_value=5)
    sync_job.run = MagicMock()

    scan_job = ScanJob()
    scan_job.secs_until_next_run = MagicMock(return_value=2)
    scan_job.run = MagicMock()

    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[sync_job]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[scan_job]),
        patch("gitrelay.daemon.time.sleep") as mock_sleep,
    ):

        # Break loop after processing all jobs
        mock_config.reload.side_effect = [False, False, False, StopLoop()]

        with pytest.raises(StopLoop):
            daemon_start()

        assert sync_job.run.called
        assert scan_job.run.called

        # Verify sleeps occurred for the correct intervals
        # Scan job (2s) is at the end of reverse-sorted list [sync(5), scan(2)], so it pops first.
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(5)


def test_daemon_loop_disabling_mid_cycle(mock_config):
    """Verifies that disabling sync mid-cycle prevents remaining sync jobs from running."""
    job1 = SyncJob()
    job1.secs_until_next_run = MagicMock(return_value=1)
    job1.run = MagicMock()

    job2 = SyncJob()
    job2.secs_until_next_run = MagicMock(return_value=2)
    job2.run = MagicMock()

    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[job1, job2]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[]),
        patch("gitrelay.daemon.time.sleep"),
    ):

        # We want job1 to run, then flip sync_enabled to False
        def flip_config():
            mock_config.sync_enabled = False
            return True

        # 1. Top of loop reload -> False
        # 2. Reload after job1 pop -> True (flips config)
        # 3. Reload after inner loop finishes -> Stop
        mock_config.reload.side_effect = [False, flip_config, StopLoop()]

        with pytest.raises(StopLoop):
            daemon_start()

        assert job1.run.called
        assert not job2.run.called


def test_daemon_idle_sleep_when_no_jobs(mock_config):
    """Verifies that daemon sleeps for idle_sleep_secs when no jobs are found."""
    mock_config.idle_sleep_secs = 42

    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[]),
        patch("gitrelay.daemon.time.sleep") as mock_sleep,
    ):

        mock_config.reload.side_effect = [False, StopLoop()]

        with pytest.raises(StopLoop):
            daemon_start()

        mock_sleep.assert_called_once_with(42)
