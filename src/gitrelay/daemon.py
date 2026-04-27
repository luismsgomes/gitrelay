# gitrelay: Sync git repos with smart scheduling and systemd integration.
# Copyright (C) 2026  Luís Gomes
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import signal
import sys
import time

from .config import MainConfig
from .scan_jobs import ScanJob, get_scan_jobs
from .sync_jobs import SyncJob, get_sync_jobs

logger = logging.getLogger(__name__)


def daemon_start(dry_run: bool = False):
    """Starts the background synchronization daemon loop."""

    def handle_sigterm(signum, frame):
        logger.info("Daemon stopping (received SIGTERM)")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    logger.info("Daemon starting...")
    try:
        try:
            config = MainConfig.load()
            config.setup_logging()
        except FileNotFoundError:
            config = MainConfig()
            config.save()
            config.setup_logging()
            logger.warning(
                "Configuration not found. Initialized defaults at %s",
                MainConfig.get_config_path(),
            )

        while True:
            if config.reload():
                config.setup_logging()

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
                if config.reload():
                    config.setup_logging()

                if isinstance(job, SyncJob):
                    if config.sync_enabled:
                        if dry_run:
                            logger.info("[DRY RUN] Would run %s", job)
                        else:
                            job.run()
                    else:
                        jobs = [j for j in jobs if not isinstance(j, SyncJob)]
                elif isinstance(job, ScanJob):
                    if config.scan_enabled:
                        if dry_run:
                            logger.info("[DRY RUN] Would run %s", job)
                        else:
                            job.run()
                    else:
                        jobs = [j for j in jobs if not isinstance(j, ScanJob)]

            if dry_run:
                time.sleep(config.idle_sleep_secs)

    except KeyboardInterrupt:
        logger.info("Daemon stopping (interrupted by user)")
        sys.exit(0)
    except Exception as e:
        logger.critical("Daemon crashed: %s", e, exc_info=True)
        sys.exit(1)
