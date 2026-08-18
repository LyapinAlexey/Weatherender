import os

from apscheduler.schedulers.background import BackgroundScheduler

from dbclear import clear
from logging_config import logging
from models import SessionLocal

LOCK_PATH = "/tmp/dbclear_scheduler.lock"
logger = logging.getLogger(__name__)


def try_acquire_leadership(lock_path: str) -> bool:
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def run_dbclear_job() -> None:
    session = SessionLocal()
    try:
        clear(session)
        logger.info("Weekly database clear job executed successfully.")
    except Exception as e:
        logger.exception(f"Error executing weekly database clear job: {e}")
    finally:
        session.close()


def init_scheduler() -> None:
    if not try_acquire_leadership(LOCK_PATH):
        logger.info("Skipping scheduler initialization: another worker is the leader.")
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_dbclear_job, "interval", days=7)
    scheduler.start()
    logger.info("Scheduler started successfully")
