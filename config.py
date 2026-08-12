import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
    WEATHER_URL = "https://api.weatherapi.com/v1/forecast.json"
    IP_GEO_URL = "https://ip-api.com"
    SECRET_KEY = os.getenv("SECRET_KEY", "default-fallback-key")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    DATABASE_URL = os.getenv("DATABASE_URL")
    REDIS_URL = os.getenv("REDIS_URL", "redis://cache:6379")
    REDIS_TTL = int(os.getenv("REDIS_TTL", 300))

    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY is not set. Add it to your .env file (see .env.example)."
            )
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if cls.LOG_LEVEL not in valid_levels:
            raise RuntimeError(
                f"Invalid LOG_LEVEL '{cls.LOG_LEVEL}'. "
                f"Must be one of: {', '.join(sorted(valid_levels))}."
            )
