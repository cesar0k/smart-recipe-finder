import pytest
import httpx
import asyncio
import os
from pathlib import Path
from httpx import ASGITransport
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import delete
from sqlalchemy_utils import database_exists, drop_database, create_database

from app.models import *
from tests.test_config import test_settings
from app.core.vector_store import VectorStore 

RECIPES_SOURCE_PATH = Path(__file__).parent.parent / "datasets" / "recipe_samples.json"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def set_test_settings():
    os.environ["MYSQL_DATABASE"] = test_settings.TEST_DB_NAME
    os.environ["CHROMA_COLLECTION_NAME"] = "recipes_test_collection"

@pytest.fixture(scope="session", autouse=True)
def prepare_db():
    if database_exists(test_settings.SYNC_TEST_DATABASE_ADMIN_URL):
        drop_database(test_settings.SYNC_TEST_DATABASE_ADMIN_URL)
    create_database(test_settings.SYNC_TEST_DATABASE_ADMIN_URL)
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_settings.ASYNC_TEST_DATABASE_ADMIN_URL)
    command.upgrade(alembic_cfg, "head")
    
    yield
    
    drop_database(test_settings.SYNC_TEST_DATABASE_ADMIN_URL)

@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(test_settings.ASYNC_TEST_DATABASE_ADMIN_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="session")
def test_vector_store():
    store = VectorStore(force_new=True)
    yield store
    try:
        store.client.delete_collection(store.collection_name)
    except:
        pass

@pytest.fixture(scope="function")
async def async_client(db_engine, test_vector_store, monkeypatch, request):
    from app.main import app
    from app.db.session import get_db
    
    monkeypatch.setattr("app.services.recipe_service.vector_store", test_vector_store)
    monkeypatch.setattr("app.core.vector_store.vector_store", test_vector_store)

    is_eval_test = request.node.get_closest_marker("eval") is not None or \
                   request.node.get_closest_marker("no_db_cleanup") is not None

    if not is_eval_test:
        test_vector_store.clear()
        async with db_engine.begin() as conn:
            await conn.execute(delete(recipe_ingredient_association))
            await conn.execute(delete(Ingredient))
            await conn.execute(delete(Recipe))

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_sessionmaker(bind=db_engine, expire_on_commit=False)() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()