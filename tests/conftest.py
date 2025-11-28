import pytest
import httpx
import asyncio
from httpx import ASGITransport
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text, delete

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
    SYNC_ADMIN_DB_URL = (
        f"mysql+pymysql://root:{settings.MYSQL_ROOT_PASSWORD}@"
        f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    admin_engine = create_engine(SYNC_ADMIN_DB_URL)

    Base.metadata.create_all(admin_engine)

    with admin_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(1) IndexIsThere FROM INFORMATION_SCHEMA.STATISTICS "
            "WHERE table_schema=DATABASE() AND table_name='recipes' AND index_name='ft_index';"
        ))
        index_exists = result.scalar()
        
        if not index_exists:
            conn.execute(text("ALTER TABLE recipes ADD FULLTEXT INDEX ft_index (title, instructions)"))
        conn.commit()

    yield

    admin_engine.dispose()

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