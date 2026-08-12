from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import Config

engine = create_engine(Config.DATABASE_URL)  # type: ignore[arg-type]
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class WeatherRequest(Base):
    __tablename__ = "weather_requests"

    id = Column(Integer, primary_key=True)
    city = Column(String(100), nullable=False)
    source = Column(String(10), nullable=False)
    temp_c = Column(Float, nullable=True)
    condition = Column(String(100), nullable=True)
    success = Column(Integer, nullable=False, default=1)
    error_message = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
