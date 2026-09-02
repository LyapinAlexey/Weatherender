import importlib
import sys

import pytest

import weatherender.config
from weatherender.config import Config


class TestConfig:
    @pytest.fixture(autouse=True)
    def _restore_config(self):
        yield
        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])

    def test_url_gets_normalized(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host/db")
        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])
        else:
            pass

        from weatherender.config import Config

        assert Config.DATABASE_URL.startswith("postgresql://")

    def test_url_normal(self):
        assert Config.DATABASE_URL is not None
        assert "postgresql" in Config.DATABASE_URL

    def test_url_is_none(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
        importlib.reload(weatherender.config)
        assert weatherender.config.Config.DATABASE_URL is None
