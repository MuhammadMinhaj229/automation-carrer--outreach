"""
ACIOS Standalone Durable Background Worker.
Processes queued discovery scans, mailbox audits, and approved outreach jobs
outside HTTP request threads.
"""

import logging
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from acios.core.job_queue import DurableJobQueue
from acios.core.repository import CareerRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ACIOS-WORKER] %(levelname)s %(message)s",
)
logger = logging.getLogger("acios.worker")

_RUNNING = True


def _handle_signal(signum, _frame):
    global _RUNNING
    logger.info("Received signal %s; shutting down worker gracefully.", signum)
    _RUNNING = False


def run_worker(poll_interval: float = 2.0) -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    repo = CareerRepository()
    queue = DurableJobQueue(repo=repo)
    logger.info(
        "ACIOS durable worker started (storage=%s, redis_configured=%s)",
        repo.storage_engine,
        bool(queue.redis_url),
    )

    while _RUNNING:
        job = queue.process_next()
        if job:
            logger.info(
                "Processed job %s (%s) -> status=%s",
                job.get("job_id"),
                job.get("job_type"),
                job.get("status"),
            )
        else:
            queue.wait_for_notification(poll_interval)


if __name__ == "__main__":
    run_worker()
