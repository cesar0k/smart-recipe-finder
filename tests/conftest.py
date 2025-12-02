import pytest
import httpx
import asyncio
import os
from httpx import ASGITransport
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, delete
from sqlalchemy_utils import database_exists, drop_database, create_database

from app.models.base import Base
from app.models.recipe import Recipe
from app.models.ingredient import Ingredient
from app.models.recipe_ingredient_association import recipe_ingredient_association
from app.core.config import settings

TEST_DB_NAME = "recipes_test_db"

@pytest.fixture(scope="session", autouse=True)
def set_test_settings():
    os.environ["MYSQL_DATABASE"] = TEST_DB_NAME

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def prepare_db():
    SYNC_TEST_DB_URL = (
        f"mysql+pymysql://root:{settings.MYSQL_ROOT_PASSWORD}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{TEST_DB_NAME}"
    )
    if database_exists(SYNC_TEST_DB_URL):
        drop_database(SYNC_TEST_DB_URL)
    create_database(SYNC_TEST_DB_URL)
    
    TEST_ASYNC_DATABASE_URL = (
        f"mysql+asyncmy://root:{settings.MYSQL_ROOT_PASSWORD}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{TEST_DB_NAME}"
    )
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_ASYNC_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
    
    yield
    
    drop_database(SYNC_TEST_DB_URL)

@pytest.fixture(scope="session")
async def db_engine():
    TEST_ASYNC_DATABASE_URL = (
        f"mysql+asyncmy://root:{settings.MYSQL_ROOT_PASSWORD}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{TEST_DB_NAME}"
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

    TestSessionLocal = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()