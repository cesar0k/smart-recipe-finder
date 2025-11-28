import pytest
import json
from httpx import AsyncClient
from pathlib import Path

BASE_TEST_PATH = Path(__file__).parents[2] / "datasets" / "test_data.json"
FILTER_DATASET_PATH = Path(__file__).parents[2] / "datasets" / "filter_test_data.json"
RECIPES_SOURCE_PATH = Path(__file__).parents[2] / "datasets" / "recipe_samples.json"
NLS_DATASET_PATH = Path(__file__).parents[2] / "datasets" / "evaluation_nls_queries.json"

with open(BASE_TEST_PATH) as f:
    base_data = json.load(f)

with open(FILTER_DATASET_PATH) as f:
    filter_data = json.load(f)

with open(RECIPES_SOURCE_PATH) as f:
    recipes_sample = json.load(f)
    
with open(NLS_DATASET_PATH) as f:
    natural_search_data = json.load(f)
    id_to_title = {r["id"]: r["title"] for r in recipes_sample}
    for q in natural_search_data:
        expected_title = id_to_title.get(q["expected_id"])
        q["should_contain"] = [expected_title] if expected_title else []
    
@pytest.mark.smoke
@pytest.mark.asyncio
class TestRecipeSmoke:
    @pytest.fixture(scope="function")
    async def setup_smoke_db(self, async_client: AsyncClient):
        for recipe in recipes_sample:
            await async_client.post("/api/v1/recipes/", json=recipe)
            
    async def test_get_recipes_list(self, async_client: AsyncClient, setup_smoke_db):
        response = await async_client.get("/api/v1/recipes/")
        assert response.status_code == 200
        assert len(response.json()) > 0
        
    async def test_create_recipe(self, async_client: AsyncClient):
        new_recipe = {
            "title": "New Created Recipe",
            "ingredients": ["test"],
            "instructions": "test",
            "cooking_time_in_minutes": 1,
            "difficulty": "easy",
            "cuisine": "Test"
        }
        response = await async_client.post("/api/v1/recipes/", json=new_recipe)
        assert response.status_code == 201
        assert response.json()["title"] == new_recipe["title"]

@pytest.mark.eval
@pytest.mark.asyncio
class TestRecipeEvaluation:
    @pytest.fixture(scope="function", autouse=True)
    async def setup_eval_db(self, async_client: AsyncClient):
        for recipe in recipes_sample:
            r_data = recipe.copy()
            if "id" in r_data:
                del r_data["id"]
            await async_client.post("/api/v1/recipes/", json=r_data)
            
    @pytest.mark.parametrize("testcase", filter_data)
    async def test_filtering(self, async_client: AsyncClient, testcase):
        params = {
            "include_ingredients": testcase["include_ingredients"],
            "exclude_ingredients": testcase["exclude_ingredients"]
        }
        response = await async_client.get("/api/v1/recipes/", params=params)
        assert response.status_code == 200
        
        results = response.json()
        found_titles = {r["title"] for r in results}
        
        excepted = set(testcase.get("should_contain", []))
        missing = excepted - found_titles
        assert not missing, f"Failed testcase {testcase['id']}. Missing: {missing}"
        
        unwanted = set(testcase.get("should_not_contain", []))
        found_unwanted = found_titles.intersection(unwanted)
        assert not found_unwanted, f"Failed testcase {testcase['id']}. Found unwanted: {found_unwanted}"
        
    @pytest.mark.parametrize("testcase", natural_search_data)
    async def test_natural_search_quality(self, async_client: AsyncClient, testcase):
        response = await async_client.get("/api/v1/recipes/search/", params={"q": testcase['query']})
        assert response.status_code == 200
        
        results = response.json()
        found_titles = {r["title"] for r in results}
        excepted = set(testcase.get("should_contain", []))
        
        missing = excepted - found_titles
        assert not missing, f"Natutal language search, with query: {testcase['query']} failed. Expected to fing: {missing}"