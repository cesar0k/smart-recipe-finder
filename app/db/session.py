import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.config import settings

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=True, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)
