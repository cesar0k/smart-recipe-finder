import pytest
import httpx
import asyncio
from httpx import ASGITransport
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, delete

from app.models.base import Base
from app.models.recipe import Recipe
from app.models.ingredient import Ingredient
from app.models.recipe_ingredient_association import recipe_ingredient_association
from app.core.config import settings

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def prepare_db():
    SYNC_TEST_DB_URL = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", SYNC_TEST_DB_URL)
    
    command.upgrade(alembic_cfg, "head")
    yield
    
    command.downgrade(alembic_cfg, "base")

@pytest.fixture(scope="session")
async def db_engine():
    TEST_ASYNC_DATABASE_URL = (
        f"mysql+asyncmy://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def async_client(db_engine):
    from app.main import app
    from app.db.session import get_db

    async with db_engine.begin() as conn:
        await conn.execute(delete(recipe_ingredient_association))
        await conn.execute(delete(Ingredient))
        await conn.execute(delete(Recipe))

    TestSessionLocal = sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()