import os
import json
import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from gitrelay.sync_jobs import (
    SyncResult,
    CommitInfo,
    SyncJob,
    LocalRepoSyncJob,
    get_sync_jobs,
)
from gitrelay.config import LocalHubConfig, LocalRepoSyncConfig, LocalHubsConfig


@pytest.fixture
def mock_sync_log(tmp_path):
    """Provides a path to a mock sync log file."""
    log_dir = tmp_path / "logs" / "hub"
    log_dir.mkdir(parents=True)
    return log_dir / "target.jsonl"


def test_sync_result_append_and_load_last(mock_sync_log):
    """Verifies that SyncResult can save itself and load the last entry."""
    # 1. Create and save first result
    res1 = SyncResult(
        timestamp=datetime.now() - timedelta(minutes=10), errors=["first error"]
    )
    res1.append_to_log(mock_sync_log)

    # 2. Create and save second result (the one we expect to load)
    res2 = SyncResult(
        timestamp=datetime.now(),
        commits_fetched=[CommitInfo(hash="abc", timestamp=datetime.now())],
    )
    res2.append_to_log(mock_sync_log)

    # 3. Load last and verify
    loaded = SyncResult.load_last(mock_sync_log)
    assert loaded is not None
    assert loaded.timestamp.replace(microsecond=0) == res2.timestamp.replace(
        microsecond=0
    )
    assert len(loaded.commits_fetched) == 1
    assert loaded.commits_fetched[0].hash == "abc"
    assert loaded.success is True


def test_sync_result_load_from_empty_file(mock_sync_log):
    """Verifies load_last returns None for missing or empty files."""
    assert SyncResult.load_last(mock_sync_log) is None

    mock_sync_log.touch()
    assert SyncResult.load_last(mock_sync_log) is None


def test_sync_job_log_path(tmp_path):
    """Verifies that SyncJob calculates the correct log path."""
    hub = LocalHubConfig(hub_name="work/api")
    target = LocalRepoSyncConfig(
        target_alias="backup",
        sync_interval_secs=3600,
        sync_interval_adjust=False,
        local_repo_path=Path("/tmp/repo"),
    )

    # Correctly mock Path in the target module
    with patch("gitrelay.sync_jobs.Path") as mock_path:
        # Mock Path("~/.cache/gitrelay/logs/sync").expanduser() to return tmp_path
        mock_path.return_value.expanduser.return_value = tmp_path

        job = LocalRepoSyncJob(local_hub_config=hub, sync_target_config=target)

        expected_path = tmp_path / "work/api" / "backup.jsonl"
        assert job.log_path == expected_path


def test_sync_job_secs_until_next_run():
    """Verifies the scheduling logic in SyncJob."""
    hub = MagicMock(spec=LocalHubConfig)
    hub.hub_name = "test"
    target = MagicMock(spec=LocalRepoSyncConfig)
    target.target_alias = "target"
    target.sync_interval_secs = 60

    with patch("gitrelay.sync_jobs.SyncResult.load_last", return_value=None):
        job = LocalRepoSyncJob(local_hub_config=hub, sync_target_config=target)
        assert job.secs_until_next_run() == 0

    last_res = SyncResult(timestamp=datetime.now() - timedelta(seconds=10))
    with patch("gitrelay.sync_jobs.SyncResult.load_last", return_value=last_res):
        job = LocalRepoSyncJob(local_hub_config=hub, sync_target_config=target)
        # 60 - 10 = 50
        assert job.secs_until_next_run() <= 50


def test_sync_job_run_and_record(tmp_path):
    """Verifies that run() updates last_result and writes to log."""
    hub = LocalHubConfig(hub_name="test-hub")
    target = LocalRepoSyncConfig(
        target_alias="test-target",
        sync_interval_secs=3600,
        sync_interval_adjust=False,
        local_repo_path=Path("/tmp/repo"),
    )

    with patch.object(SyncJob, "log_path", new_callable=PropertyMock) as mock_log_path:
        log_file = tmp_path / "test.jsonl"
        mock_log_path.return_value = log_file

        job = LocalRepoSyncJob(local_hub_config=hub, sync_target_config=target)
        assert job.last_result is None

        job.run()

        assert job.last_result is not None
        assert job.last_result.success is True
        assert log_file.exists()
        content = log_file.read_text()
        assert "timestamp" in content


def test_get_sync_jobs_complex_config(tmp_path):
    """Verifies that get_sync_jobs correctly parses LocalHubsConfig."""
    hubs_path = tmp_path / "hubs.json"

    with patch(
        "gitrelay.config.LocalHubsConfig.get_config_path", return_value=hubs_path
    ):
        hub = LocalHubConfig(hub_name="my-hub")
        hub.add_synced_local_repo(
            LocalRepoSyncConfig(
                target_alias="repo1",
                sync_interval_secs=3600,
                sync_interval_adjust=False,
                local_repo_path=Path("/tmp/r1"),
            )
        )

        hubs_config = LocalHubsConfig(local_hubs=[hub])
        hubs_config.save()

        jobs = get_sync_jobs()
        assert len(jobs) == 1
        assert isinstance(jobs[0], LocalRepoSyncJob)
        assert jobs[0].sync_target_config.target_alias == "repo1"
