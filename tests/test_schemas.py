import pytest
from marshmallow import ValidationError

from weatherender.schemas import CityRequestSchema


class TestSchemas:
    def test_valid_city(self):
        schema = CityRequestSchema()
        res = schema.load({"city": "Berlin"})
        assert res["city"] == "Berlin"

    def test_city_min_length_boundary(self):
        schema = CityRequestSchema()
        res = schema.load({"city": "a"})
        assert res["city"] == "a"

    def test_city_max_length_boundary(self):
        schema = CityRequestSchema()
        res = schema.load({"city": "a" * 100})
        assert res["city"] == "a" * 100

    def test_missing_city_raises_error(self):
        schema = CityRequestSchema()
        with pytest.raises(ValidationError):
            schema.load({})

    def test_empty_city_raises_error(self):
        schema = CityRequestSchema()
        with pytest.raises(ValidationError):
            schema.load({"city": ""})

    def test_city_too_long_raises_error(self):
        schema = CityRequestSchema()
        with pytest.raises(ValidationError):
            schema.load({"city": "a" * 101})
