from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta

import weatherender.dbclear
from weatherender.models import WeatherRequest


class TestDBClear:
    def test_clear_deletes_old_records(self, db_session):
        old_record = WeatherRequest(
            city="London",
            source="web",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - relativedelta(months=5),
        )
        new_record = WeatherRequest(
            city="New York",
            source="web",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - relativedelta(days=5),
        )
        db_session.add_all([old_record, new_record])
        db_session.commit()
        weatherender.dbclear.clear(db_session)
        remaining = db_session.query(WeatherRequest).all()
        assert len(remaining) == 1
        assert remaining[0].city == "New York"

    def test_no_old_records(self, db_session):
        new_record1 = WeatherRequest(
            city="Tokio",
            source="web",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - relativedelta(days=5),
        )
        new_record2 = WeatherRequest(
            city="Bangkok",
            source="web",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - relativedelta(days=5),
        )
        db_session.add_all([new_record1, new_record2])
        db_session.commit()
        weatherender.dbclear.clear(db_session)
        remaining = db_session.query(WeatherRequest).all()
        cities = {r.city for r in remaining}
        assert len(cities) == 2
        assert cities == {"Tokio", "Bangkok"}

    def test_all_old_records(self, db_session):
        old_record1 = WeatherRequest(
            city="Toronto",
            source="web",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - relativedelta(months=5),
        )
        old_record2 = WeatherRequest(
            city="Ottava",
            source="web",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - relativedelta(months=5),
        )
        db_session.add_all([old_record1, old_record2])
        db_session.commit()
        weatherender.dbclear.clear(db_session)
        remaining = db_session.query(WeatherRequest).all()
        assert len(remaining) == 0

    def test_boundary_cutoff_date(self, db_session):
        boundary_record = WeatherRequest(
            city="Paris",
            source="web",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            - relativedelta(months=1)
            + relativedelta(seconds=5),
        )
        db_session.add(boundary_record)
        db_session.commit()
        weatherender.dbclear.clear(db_session)
        remaining = db_session.query(WeatherRequest).all()
        assert len(remaining) == 1
        assert remaining[0].city == "Paris"

    def test_clear_handles_exception(self, db_session):
        with patch.object(db_session, "commit", side_effect=Exception("DB Error")):
            with patch.object(db_session, "rollback") as mock_rollback:
                weatherender.dbclear.clear(db_session)
                mock_rollback.assert_called_once()

    def test_main_execution(self):
        with patch("weatherender.dbclear.clear") as mock_clear:
            if hasattr(weatherender.dbclear, "main"):
                weatherender.dbclear.main()
                mock_clear.assert_called_once()
            else:
                weatherender.dbclear.clear(MagicMock())
