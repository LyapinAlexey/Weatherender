"""
Weatherender — production-grade weather intelligence for skiers.
"""

__version__ = "2.0.0"
__author__ = "Alexey Lyapin"

from weatherender.API import main as api
from weatherender.cache import CacheService
from weatherender.CLI import main as cli
from weatherender.config import Config
from weatherender.dbclear import clear
from weatherender.logging_config import setup_logging
from weatherender.models import Base, WeatherRequest
from weatherender.schemas import CityRequestSchema
from weatherender.services import WeatherService
from weatherender.snow import get_snow_state
from weatherender.WEB import app as web

__all__ = [
    "api",
    "cli",
    "web",
    "Config",
    "Base",
    "WeatherRequest",
    "WeatherService",
    "get_snow_state",
    "CacheService",
    "CityRequestSchema",
    "setup_logging",
    "clear",
    "__version__",
    "__author__",
]
