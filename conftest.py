import os
from typing import Any, Generator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from API import app as api_app
from models import Base
from WEB import app as flask_app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if TEST_DATABASE_URL is None:
    raise ValueError("TEST_DATABASE_URL environment variable is not set")


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    TestSessionLocal = sessionmaker(bind=connection)
    session = TestSessionLocal()
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client() -> Generator[Any, None, None]:
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def fake_weather_response() -> dict:
    return {
        "location": {
            "localtime": "2026-07-16 12:00",
            "name": "Berlin",
            "country": "Germany",
            "region": "Berlin",
        },
        "current": {
            "temp_c": 20,
            "condition": {"text": "Sunny"},
            "uv": 5,
            "pressure_mb": 760,
        },
        "forecast": {
            "forecastday": [
                {
                    "date": "2026-07-16",
                    "day": {
                        "avgtemp_c": 22,
                        "totalprecip_mm": 0,
                        "uv": 5,
                        "maxwind_kph": 10,
                        "gust_kph": 15,
                    },
                    "hour": [
                        {
                            "time": "2026-07-16 12:00",
                            "temp_c": 20,
                            "chance_of_rain": 0,
                            "chance_of_snow": 0,
                            "uv": 5,
                            "pressure_mb": 1013,
                        }
                    ],
                }
            ]
        },
    }


@pytest_asyncio.fixture
async def api_client():
    async with api_app.router.lifespan_context(api_app):
        transport = ASGITransport(app=api_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
