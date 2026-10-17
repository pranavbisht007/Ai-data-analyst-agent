"""
run_scheduler.py
Persistent background scheduler process.
Run this separately from the Streamlit app:

    python run_scheduler.py

Scheduled jobs only execute while this process is running.
This must be running on the machine — cloud scheduling is not used.
"""
from __future__ import annotations

import logging
import signal
import sys
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from config.settings import DATABASE_URL, SCHEDULER_TIMEZONE
from src.database.db import init_db

logger = logging.getLogger(__name__)

# Initialise DB tables before scheduler starts
init_db()

jobstores = {
    "default": SQLAlchemyJobStore(url=DATABASE_URL),
}
executors = {
    "default": ThreadPoolExecutor(max_workers=2),
}

scheduler = BlockingScheduler(
    jobstores=jobstores,
    executors=executors,
    timezone=SCHEDULER_TIMEZONE,
    job_defaults={
        "coalesce": True,         # merge missed runs into one
        "max_instances": 1,       # never run the same job twice simultaneously
        "misfire_grace_time": 300,
    },
)


def _shutdown(signum, frame):
    logger.info("Scheduler shutting down (signal %d)...", signum)
    scheduler.shutdown(wait=False)
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


if __name__ == "__main__":
    logger.info(
        "Scheduler starting. Timezone: %s. "
        "Add jobs via the Streamlit UI or by calling scheduler.add_job() here.",
        SCHEDULER_TIMEZONE,
    )
    logger.info(
        "NOTE: Scheduled alerts only fire while this process is running "
        "and the computer is awake."
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
