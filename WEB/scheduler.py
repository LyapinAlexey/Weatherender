import os

from apscheduler.schedulers.background import BackgroundScheduler

from dbclear import clear
from models import SessionLocal

LOCK_PATH = "/tmp/dbclear_scheduler.lock"


def try_acquire_leadership(lock_path: str) -> bool:
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def run_dbclear_job() -> None:
    session = SessionLocal()
    clear(session)


def init_scheduler() -> None:
    if not try_acquire_leadership(LOCK_PATH):
        return

    schelduler = BackgroundScheduler()
    schelduler.add_job(run_dbclear_job, "interval", days=7)
    schelduler.start()
