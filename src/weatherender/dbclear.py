import logging
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from weatherender.logging_config import setup_logging
from weatherender.models import SessionLocal, WeatherRequest

setup_logging()
logger = logging.getLogger(__name__)


def clear(session: Session) -> None:
    # datetime.now(timezone.utc) + replace(tzinfo=None) instead of deprecated utcnow();
    # stays naive to match models.py created_at (which is also naive) — avoiding schema migration
    cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - relativedelta(
        months=1
    )
    db_session = session
    try:
        result = (
            db_session.query(WeatherRequest)
            .filter(WeatherRequest.created_at < cutoff_date)
            .delete()
        )
        db_session.commit()
        logger.info(f"Cleared files: {result}")
    except Exception:
        logger.exception("Error while clearing database")
        db_session.rollback()
    finally:
        db_session.close()


if __name__ == "__main__":
    session = SessionLocal()
    clear(session)
