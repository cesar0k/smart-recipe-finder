import pytest
import json
from httpx import AsyncClient
from pathlib import Path

TEST_DATA_PATH = Path(__file__).parent.parent.parent / "test_data.json"
with open(TEST_DATA_PATH) as f:
    test_data = json.load(f)
    
RECIPES_PATH = Path(__file__).parent.parent.parent / "recipe_samples.json"
with open(RECIPES_PATH) as f:
    recipes_sample = json.load(f)
    
@pytest.mark.asyncio
class TestRecipeSearch:
    @pytest.fixture(scope="function")
    async def setup_db_with_recipes(self, async_client: AsyncClient):
        for recipe in recipes_sample:
            await async_client.post("/api/v1/recipes/", json=recipe)
            
    @pytest.mark.parametrize("testcase", test_data["include_exclude_testcases"])
    async def test_include_exclude_filtering(self, async_client: AsyncClient, setup_db_with_recipes, testcase):
        params = {
            "include_ingredients": testcase["include_ingredients"],
            "exclude_ingredients": testcase["exclude_ingredients"],
        }
        response = await async_client.get("api/v1/recipes/", params=params)
        assert response.status_code == 200
        
        results = response.json()
        found_titles = {recipe["title"] for recipe in results}
        
        expected_titles = set(testcase.get("should-contain", []))
        assert expected_titles.issubset(found_titles), \
            f"Failed to find expected recipes. Missing: {expected_titles - found_titles}"
            
        unexpected_titles = set(testcase.get("should-not-contain", []))
        found_unexpected = found_titles.intersection(unexpected_titles)
        assert not found_unexpected, \
            f"Found unexpected recipes: {found_unexpected}"
            
    @pytest.mark.parametrize("testcase", test_data["natural_search_testcases"])
    async def test_natural_language_search(self, async_client: AsyncClient, setup_db_with_recipes, testcase):
        response = await async_client.get("api/v1/recipes/search/", params={"q": testcase["query"]})
        assert response.status_code == 200
        
        results = response.json()
        found_titles = {recipe["title"] for recipe in results}
        
        expected_titles = set(testcase.get("should_contain", []))
        assert expected_titles.issubset(found_titles), \
            f"Query {testcase['query']} missed: {expected_titles - found_titles}"
            
        unexpected_titles = set(testcase.get("should_not_contain", []))
        found_unexpected = found_titles.intersection(unexpected_titles)
        assert not found_unexpected, \
            f"Query {testcase['query']} return unexpected recipes: {found_unexpected}"