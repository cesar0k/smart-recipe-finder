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
    
@pytest.mark.asyncio
class TestRecipeOperations:
    BASE_RECIPE_DATA = {
        "title": "Standard Recipe",
        "ingredients": ["ingredient A", "ingredient B"],
        "instructions": "Mix and cook.",
        "cooking_time_in_minutes": 30,
        "difficulty": "medium",
        "cuisine": "TestCuisine"
    }

    @pytest.fixture
    async def existing_recipe(self, async_client: AsyncClient):
        response = await async_client.post("/api/v1/recipes/", json=self.BASE_RECIPE_DATA)
        assert response.status_code == 201
        return response.json()

    @pytest.mark.smoke
    async def test_create_recipe(self, async_client: AsyncClient):
        new_recipe = self.BASE_RECIPE_DATA.copy()
        new_recipe["title"] = "New Created Recipe"
        
        response = await async_client.post("/api/v1/recipes/", json=new_recipe)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == new_recipe["title"]
        assert data["id"] is not None

    @pytest.mark.smoke
    async def test_get_recipes_list(self, async_client: AsyncClient, existing_recipe):
        response = await async_client.get("/api/v1/recipes/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        ids = [r["id"] for r in data]
        assert existing_recipe["id"] in ids

    @pytest.mark.smoke
    async def test_get_recipe_by_id(self, async_client: AsyncClient, existing_recipe):
        recipe_id = existing_recipe["id"]
        response = await async_client.get(f"/api/v1/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == existing_recipe["title"]

    async def test_get_recipe_not_found(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/recipes/999999")
        assert response.status_code == 404

    async def test_update_recipe_partial(self, async_client: AsyncClient, existing_recipe):
        recipe_id = existing_recipe["id"]
        update_payload = {"title": "Updated Title", "difficulty": "hard"}
        
        response = await async_client.patch(f"/api/v1/recipes/{recipe_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == update_payload["title"]
        assert data["difficulty"] == update_payload["difficulty"]
        assert data["cuisine"] == existing_recipe["cuisine"]

    async def test_update_recipe_ingredients(self, async_client: AsyncClient, existing_recipe):
        recipe_id = existing_recipe["id"]
        new_ingredients = ["new_ing1", "new_ing2"]
        
        response = await async_client.patch(
            f"/api/v1/recipes/{recipe_id}", 
            json={"ingredients": new_ingredients}
        )
        assert response.status_code == 200
        data = response.json()
        
        actual_ingredients = {ing["name"] for ing in data["ingredients"]}
        assert actual_ingredients == set(new_ingredients)

    async def test_update_recipe_not_found(self, async_client: AsyncClient):
        update_payload = {"title": "Ghost Recipe"}
        response = await async_client.patch("/api/v1/recipes/999999", json=update_payload)
        assert response.status_code == 404

    async def test_delete_recipe(self, async_client: AsyncClient, existing_recipe):
        recipe_id = existing_recipe["id"]
        response = await async_client.delete(f"/api/v1/recipes/{recipe_id}")
        assert response.status_code == 200

        get_response = await async_client.get(f"/api/v1/recipes/{recipe_id}")
        assert get_response.status_code == 404
        
    async def test_delete_recipe_not_found(self, async_client: AsyncClient):
        response = await async_client.delete("/api/v1/recipes/999999")
        assert response.status_code == 404

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