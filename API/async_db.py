from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import Config

if Config.DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set, cannot build ASYNC_DATABASE_URL")
ASYNC_DATABASE_URL = Config.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://", 1
)

engine = create_async_engine(ASYNC_DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
