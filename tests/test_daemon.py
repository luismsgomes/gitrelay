import pytest
import time
from unittest.mock import patch, MagicMock
from gitrelay.daemon import daemon_start
from gitrelay.config import MainConfig, LocalHubConfig, SyncBaseConfig
from gitrelay.sync_jobs import SyncJob
from gitrelay.scan_jobs import ScanJob


class StopLoop(Exception):
    """
    Custom exception used to break the infinite 'while True' loop in the daemon.

    Testing infinite loops is tricky because they never return. By configuring
    a mock to raise this exception, we can force the loop to exit exactly when
    we want and catch it in the test to resume execution.
    """

    pass


class MockSyncJob(SyncJob[SyncBaseConfig]):
    """
    A concrete implementation of the abstract SyncJob class for testing.

    Since SyncJob is abstract (cannot be instantiated), we need this mock
    class to provide a simple implementation of the required '_run' method.
    """

    def _run(self, result) -> None:
        pass


@pytest.fixture
def mock_config():
    """
    A pytest fixture that creates a pre-configured mock of MainConfig.

    Fixtures allow us to share common setup code across multiple tests.
    This mock mimics the configuration object that the daemon expects to load.
    """
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
    1. Fetches jobs from get_sync_jobs and get_scan_jobs.
    2. Sorts them correctly (running shorter intervals first).
    3. Executes the 'run' method of each job.
    """
    # 1. SETUP: Create fake jobs with specific execution intervals.
    # Sync job wants to run in 5 seconds.
    hub_config = MagicMock(spec=LocalHubConfig)
    hub_config.hub_name = "test-hub"

    job_config = MagicMock(spec=SyncBaseConfig)
    job_config.target_alias = "test-target"
    job_config.sync_interval_secs = 3600

    sync_job = MockSyncJob(local_hub_config=hub_config, sync_target_config=job_config)
    sync_job.secs_until_next_run = MagicMock(return_value=5)
    sync_job._run = MagicMock()

    # Scan job wants to run in 2 seconds.
    scan_job = ScanJob()
    scan_job.secs_until_next_run = MagicMock(return_value=2)
    scan_job.run = MagicMock()

    # 2. MOCKING: Replace external modules/methods with controlled mocks.
    # patch(...) intercepts calls to these functions and returns our fake data instead.
    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[sync_job]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[scan_job]),
        patch("gitrelay.daemon.time.sleep") as mock_sleep,
    ):

        # 3. ORCHESTRATION: Control the flow of the infinite loop.
        # We tell mock_config.reload() to:
        # - Return False on 1st call (inside 'while True')
        # - Return False on 2nd call (inside 'while jobs' for 1st job)
        # - Return False on 3rd call (inside 'while jobs' for 2nd job)
        # - Raise StopLoop on 4th call (when it loops back to the Top)
        mock_config.reload.side_effect = [False, False, False, StopLoop()]

        # 4. EXECUTION: Run the daemon and expect it to "crash" with StopLoop.
        with pytest.raises(StopLoop):
            daemon_start()

        # 5. VERIFICATION: Ensure the daemon behaved as expected.
        assert sync_job._run.called
        assert scan_job.run.called
        assert sync_job.last_result is not None

        # Verify sleeps occurred for the correct intervals.
        # Your logic sorts (sync:5, scan:2) -> pops END of list.
        # Reverse sort results in [sync(5), scan(2)], so scan(2) is popped and run FIRST.
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(5)


def test_daemon_loop_disabling_mid_cycle(mock_config):
    """
    Verifies the future-proof filtering logic:
    If the config is reloaded mid-cycle and 'sync_enabled' becomes False,
    the remaining SyncJobs in the current list should be skipped.
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
    ):

        # This function will be triggered by mock_config.reload()
        def flip_config():
            # Mid-cycle, the user "manually" disables syncing
            mock_config.sync_enabled = False
            return True  # Indicates to the daemon that a change occurred

        # CONTROL:
        # 1. Top of loop reload -> False
        # 2. Reload after job1 pop -> True (triggers flip_config)
        # 3. Reload after inner loop finishes (back at top) -> Stop
        mock_config.reload.side_effect = [False, flip_config, StopLoop()]

        with pytest.raises(StopLoop):
            daemon_start()

        # Verify result: job1 ran, but job2 was correctly filtered out and skipped.
        assert job1._run.called
        assert not job2._run.called


def test_daemon_idle_sleep_when_no_jobs(mock_config):
    """
    Verifies that the daemon doesn't crash when there are no jobs,
    and instead enters an "idle sleep" state.
    """
    mock_config.idle_sleep_secs = 42

    with (
        patch("gitrelay.daemon.MainConfig.load", return_value=mock_config),
        patch("gitrelay.daemon.get_sync_jobs", return_value=[]),
        patch("gitrelay.daemon.get_scan_jobs", return_value=[]),
        patch("gitrelay.daemon.time.sleep") as mock_sleep,
    ):

        # Break the loop immediately on the second pass
        mock_config.reload.side_effect = [False, StopLoop()]

        with pytest.raises(StopLoop):
            daemon_start()

        # Verify the daemon waited for the configured idle time
        mock_sleep.assert_called_once_with(42)
