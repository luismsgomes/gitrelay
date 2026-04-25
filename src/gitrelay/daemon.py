import time
import logging
from .config import MainConfig
from .sync_jobs import get_sync_jobs, SyncJob
from .scan_jobs import get_scan_jobs, ScanJob

logger = logging.getLogger(__name__)


def daemon_start():
    config = MainConfig.load()

    while True:
        config.reload()

        jobs = []
        if config.sync_enabled:
            jobs.extend(get_sync_jobs())
        if config.scan_enabled:
            jobs.extend(get_scan_jobs())
        if not jobs:
            time.sleep(config.idle_sleep_secs)
            continue

        # reverse sort because we will process one by one always poping the last from the list
        jobs.sort(key=lambda job: job.secs_until_next_run(), reverse=True)

        while jobs:
            job = jobs.pop()
            secs = job.secs_until_next_run()
            logger.debug("Sleeping for %d seconds until next job", secs)
            time.sleep(secs)

            # Reload config again right before running each job (reloads only if file changed)
            config.reload()

            if isinstance(job, SyncJob):
                if config.sync_enabled:
                    job.run()
                else:
                    jobs = [j for j in jobs if not isinstance(j, SyncJob)]
            elif isinstance(job, ScanJob):
                if config.scan_enabled:
                    job.run()
                else:
                    jobs = [j for j in jobs if not isinstance(j, ScanJob)]
