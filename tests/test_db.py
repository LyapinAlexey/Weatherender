import pytest
from sqlalchemy.exc import IntegrityError

from weatherender.models import WeatherRequest


class TestDB:
    def test_create_and_read_weather_request(self, db_session):
        request = WeatherRequest(
            city="Berlin", source="web", temp_c=20, condition="sunny", success=1
        )
        db_session.add(request)
        db_session.commit()
        found = db_session.query(WeatherRequest).filter_by(city="Berlin").first()
        assert found is not None
        assert found.city == "Berlin"
        assert found.temp_c == 20
        assert found.condition == "sunny"

    def test_missing_required_field_raises_integrity_error(self, db_session):
        request = WeatherRequest(source="web", success=1)
        db_session.add(request)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_defaults_are_applied_when_not_specified(self, db_session):
        request = WeatherRequest(city="London", source="web")
        db_session.add(request)
        db_session.commit()
        found = db_session.query(WeatherRequest).filter_by(city="London").first()
        assert found is not None
        assert found.success == 1
        assert found.created_at is not None

    def test_optional_fields_can_be_none(self, db_session):
        request = WeatherRequest(city="Monreal", source="web", success=0)
        db_session.add(request)
        db_session.commit()
        found = db_session.query(WeatherRequest).filter_by(city="Monreal").first()
        assert found.temp_c is None
        assert found.condition is None
        assert found.error_message is None

    @pytest.mark.parametrize("temp", [-50, 0, 45])
    def test_boundary_temperature_values(self, db_session, temp):
        request = WeatherRequest(city="Tokio", source="web", temp_c=temp, success=1)
        db_session.add(request)
        db_session.commit()
        found = db_session.query(WeatherRequest).filter_by(city="Tokio").first()
        assert found.temp_c == temp

    def test_delete_weather_request(self, db_session):
        request = WeatherRequest(city="Paris", source="web", success=1)
        db_session.add(request)
        db_session.commit()
        db_session.delete(request)
        db_session.commit()
        found = db_session.query(WeatherRequest).filter_by(city="Paris").first()
        assert found is None

    def test_update_weather_request(self, db_session):
        request = WeatherRequest(city="Monza", source="web", temp_c=15, success=1)
        db_session.add(request)
        db_session.commit()
        request.temp_c = 30
        db_session.commit()
        found = db_session.query(WeatherRequest).filter_by(city="Monza").first()
        assert found.temp_c == 30
