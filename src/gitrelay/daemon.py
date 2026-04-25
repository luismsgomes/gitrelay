import logging
import sys
import time

from .config import MainConfig
from .scan_jobs import ScanJob, get_scan_jobs
from .sync_jobs import SyncJob, get_sync_jobs

logger = logging.getLogger(__name__)


def daemon_start():
    """Starts the background synchronization daemon loop."""
    try:
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

            # reverse sort so we can pop the last from the list efficiently
            jobs.sort(key=lambda job: job.secs_until_next_run(), reverse=True)

            while jobs:
                job = jobs.pop()
                secs = job.secs_until_next_run()
                logger.debug("Sleeping for %d seconds until next job", secs)
                time.sleep(secs)

                # Reload config right before running each job (if changed on disk)
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

    except KeyboardInterrupt:
        logger.info("Daemon stopping (interrupted by user)")
        sys.exit(0)
    except Exception as e:
        logger.critical("Daemon crashed: %s", e, exc_info=True)
        sys.exit(1)
