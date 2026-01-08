import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.vector_store import VectorStore
from app.models.recipe import Recipe
from app.schemas import RecipeCreate
from app.services import recipe_service

BASE_DIR = Path(__file__).parents[3]

FILTER_DATASET_PATH = BASE_DIR / "datasets" / "filter_test_data.json"
RECIPES_SOURCE_PATH = BASE_DIR / "datasets" / "recipe_samples.json"
NLS_DATASET_PATH = BASE_DIR / "datasets" / "evaluation_nls_queries.json"

with open(FILTER_DATASET_PATH) as f:
    filter_data = json.load(f)

with open(RECIPES_SOURCE_PATH) as f:
    recipes_sample = json.load(f)

with open(NLS_DATASET_PATH) as f:
    natural_search_data = json.load(f)
    id_to_title = {r["id"]: r["title"] for r in recipes_sample}
    for q in natural_search_data:
        expected_ids = q.get("expected_ids")
        if expected_ids is None:
            expected_ids = [q["expected_id"]] if "expected_id" in q else []

        expected_titles = {
            id_to_title.get(eid) for eid in expected_ids if id_to_title.get(eid)
        }
        q["should_contain"] = list(expected_titles) if expected_titles else []


@pytest.mark.crud
@pytest.mark.asyncio
class TestRecipeOperations:
    BASE_RECIPE_DATA: dict[str, Any] = {
        "title": "Standard Recipe",
        "ingredients": ["ingredient A", "ingredient B"],
        "instructions": "Mix and cook.",
        "cooking_time_in_minutes": 30,
        "difficulty": "medium",
        "cuisine": "SomeCuisine",
    }

    @pytest.fixture
    async def existing_recipe(self, async_client: AsyncClient) -> Dict[str, Any]:
        response = await async_client.post(
            "/api/v1/recipes/", json=self.BASE_RECIPE_DATA
        )
        assert response.status_code == 201
        return cast(Dict[str, Any], response.json())

    @pytest.mark.smoke
    async def test_create_recipe(self, async_client: AsyncClient) -> None:
        new_recipe = self.BASE_RECIPE_DATA.copy()
        new_recipe["title"] = "New Created Recipe"

        response = await async_client.post("/api/v1/recipes/", json=new_recipe)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == new_recipe["title"]
        assert data["id"] is not None

    @pytest.mark.smoke
    async def test_get_recipes_list(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        response = await async_client.get("/api/v1/recipes/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        ids = [r["id"] for r in data]
        assert existing_recipe["id"] in ids

    @pytest.mark.smoke
    async def test_get_recipe_by_id(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        recipe_id = existing_recipe["id"]
        response = await async_client.get(f"/api/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == existing_recipe["title"]

    async def test_get_recipe_not_found(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        recipe_id = existing_recipe["id"]
        response = await async_client.get(f"/api/v1/recipes/{recipe_id + 1}")
        assert response.status_code == 404

    async def test_update_recipe_partial(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        recipe_id = existing_recipe["id"]
        update_payload = {"title": "Updated Title", "difficulty": "hard"}

        response = await async_client.patch(
            f"/api/v1/recipes/{recipe_id}", json=update_payload
        )
        assert response.status_code == 200
        data = response.json()

        assert data["title"] == update_payload["title"]
        assert data["difficulty"] == update_payload["difficulty"]
        assert data["cuisine"] == existing_recipe["cuisine"]

    async def test_update_recipe_ingredients(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        recipe_id = existing_recipe["id"]
        new_ingredients = ["new_ing1", "new_ing2"]

        response = await async_client.patch(
            f"/api/v1/recipes/{recipe_id}", json={"ingredients": new_ingredients}
        )
        assert response.status_code == 200
        data = response.json()

        actual_ingredients = set(ing["name"] for ing in data["ingredients"])
        assert actual_ingredients == set(new_ingredients)

    async def test_update_recipe_not_found(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        recipe_id = existing_recipe["id"]
        update_payload = {"title": "Ghost Recipe"}
        response = await async_client.patch(
            f"/api/v1/recipes/{recipe_id + 1}", json=update_payload
        )
        assert response.status_code == 404

    async def test_delete_recipe(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        recipe_id = existing_recipe["id"]
        response = await async_client.delete(f"/api/v1/recipes/{recipe_id}")
        assert response.status_code == 200

        get_response = await async_client.get(f"/api/v1/recipes/{recipe_id}")
        assert get_response.status_code == 404

    async def test_delete_recipe_not_found(
        self, async_client: AsyncClient, existing_recipe: Dict[str, Any]
    ) -> None:
        recipe_id = existing_recipe["id"]
        response = await async_client.delete(f"/api/v1/recipes/{recipe_id + 1}")
        assert response.status_code == 404


@pytest.mark.no_db_cleanup
@pytest.mark.eval
@pytest.mark.asyncio
class TestRecipeEvaluation:
    @pytest.fixture(scope="class", autouse=True)
    async def setup_search_db(
        self, db_engine: AsyncEngine, test_vector_store: VectorStore
    ) -> AsyncGenerator[None, None]:
        original_store = recipe_service.vector_store
        recipe_service.vector_store = test_vector_store

        TestSessionLocal = async_sessionmaker(
            bind=db_engine, class_=AsyncSession, expire_on_commit=False
        )

        async with TestSessionLocal() as session:
            await session.execute(delete(Recipe))
            await session.commit()

            for recipe in recipes_sample:
                r_data = recipe.copy()
                if "id" in r_data:
                    del r_data["id"]

                recipe_in = RecipeCreate(**r_data)

                await recipe_service.create_recipe(db=session, recipe_in=recipe_in)
        yield

        recipe_service.vector_store = original_store

    @pytest.mark.parametrize("testcase", filter_data)
    async def test_filtering(
        self, async_client: AsyncClient, testcase: Dict[str, Any]
    ) -> None:
        params = {
            "include_ingredients": testcase["include_ingredients"],
            "exclude_ingredients": testcase["exclude_ingredients"],
        }
        response = await async_client.get("/api/v1/recipes/", params=params)
        assert response.status_code == 200, response.text

        results = response.json()
        found_titles = {r["title"] for r in results}

        expected = set(testcase.get("should_contain", []))
        missing = expected - found_titles
        assert not missing, f"Testcase {testcase['id']} failed. Missing: {missing}"

        unwanted = set(testcase.get("should_not_contain", []))
        found_unwanted = found_titles.intersection(unwanted)
        assert not found_unwanted, (
            f"Filter testcase {testcase['id']} failed. Found unwanted: {found_unwanted}"
        )

    @pytest.mark.parametrize("testcase", natural_search_data)
    async def test_natural_search_quality(
        self, async_client: AsyncClient, testcase: Dict[str, Any]
    ) -> None:
        response = await async_client.get(
            "/api/v1/recipes/search/", params={"q": testcase["query"]}
        )

        assert response.status_code == 200, response.text

        results = response.json()

        found_titles = {r["title"] for r in results}
        expected = set(testcase.get("should_contain", []))
        found_expected = expected.intersection(found_titles)

        assert found_expected or not expected, (
            f"Query: {testcase['query']} failed. expected one of {expected}, "
            f"but found {found_titles}"
        )
