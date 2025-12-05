import sys
import os
import time
import json
import asyncio
from pathlib import Path
from typing import Sequence
from statistics import mean

sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal, AsyncSession
from app.services import recipe_service
from app.models.recipe import Recipe
from app.models.ingredient import Ingredient

from sqlalchemy import text, not_
from sqlalchemy.future import select

BASE_PATH = Path(__file__).resolve().parent.parent
DATASETS_PATH = BASE_PATH / "datasets"

NLS_QUIERIES_PATH = DATASETS_PATH / "evaluation_nls_queries.json"
FILTER_QUERIES_PATH = DATASETS_PATH / "filter_test_data.json"
RECIPES_PATH = DATASETS_PATH / "recipe_samples.json"

async def legacy_search_recipes(db: AsyncSession, *, query_str: str) -> Sequence[Recipe]:
    search_query = (
        select(Recipe).
        where(
            text("MATCH(title, instructions) AGAINST(:query IN NATURAL LANGUAGE MODE)")
        )
        .params(query=query_str)
    )
    
    result = await db.execute(search_query)
    
    return result.scalars().unique().all()

async def legacy_get_all_recipes(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    include_str: str | None = None,
    exclude_str: str | None = None,
) -> Sequence[Recipe]:
    query = select(Recipe)
    
    if include_str:
        include_list = [item.strip() for item in include_str.split(",")]
        for ingredient in include_list:
            query = query.where(
                Recipe.ingredients.any(Ingredient.name.ilike(f"%{ingredient}%"))
            )
    if exclude_str:
        exclude_list = [item.strip() for item in exclude_str.split(",")]
        for ingredient in exclude_list:
            query = query.where(
                not_(Recipe.ingredients.any(Ingredient.name.ilike(f"%{ingredient}%")))
            )
            
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().unique().all()

async def evaluate_nls_method(method_name, search_func, queries, id_to_title):
    print("----------------------------------------------------------------")
    print(f"Evaluating '{method_name}'")
    
    passed = 0
    total = len(queries)
    latencies = []
    total_reciprocal_rank = 0.0
    zero_results_count = 0
    
    category_stats = {}
    
    async with AsyncSessionLocal() as db:
        for q in queries:
            query_text = q['query']
            expected_id = q['expected_id']
            expected_title = id_to_title.get(expected_id)
            category = q.get("category", "unknown")
            
            if category not in category_stats:
                category_stats[category] = {"total": 0, "passed": 0}
                
            start_time = time.time()
            results = await search_func(db=db, query_str=query_text)
            end_time = time.time()
            latencies.append((end_time - start_time) * 1000)

            if not results:
                zero_results_count += 1
            
            found_titles = [r.title for r in results]
            
            is_passed = expected_title in found_titles
            category_stats[category]["total"] += 1
            if is_passed:
                passed += 1
                category_stats[category]["passed"] += 1
                rank = found_titles.index(expected_title) + 1
                total_reciprocal_rank += 1.0 / rank
            else:
                # Extended log
                # print(f"Missed: '{query_text}', category: {category}, found titles: {found_titles}")
                
                # Or pass
                pass
                
    accuracy = (passed / total) * 100
    avg_latency = mean(latencies)
    mean_reciprocal_rank = total_reciprocal_rank / total if total > 0 else 0.0
    zero_result_rate = (zero_results_count / total) * 100 if total > 0 else 0.0
    
    print(f"By category:")
    for cat, stats in category_stats.items():
        cat_acc = (stats['passed'] / stats['total']) * 100
        print(f" - {cat}: {cat_acc:.2f}% ({stats['passed']}/{stats['total']} queries passed)")
    print(f"Overall Accuracy: {accuracy}% ({passed}/{total})")
    print(f"Average latency: {avg_latency:.5f} ms")
    print(f"Mean Reciprocal Rank (MRR): {mean_reciprocal_rank:.5f}")
    print(f"Zero Result Rate (ZRR): {zero_result_rate:.2f}%")
    print("----------------------------------------------------------------")
    
    return accuracy, mean_reciprocal_rank, zero_result_rate

async def evaluate_filters(method_name, filter_func, filter_queries):
    print(f"Evaluating filter with {method_name}")
    
    passed = 0
    total = len(filter_queries)
    latencies = []
    
    async with AsyncSessionLocal() as db:
        for case in filter_queries:
            start_time = time.time()
            results = await filter_func(
                db=db,
                include_str = case["include_ingredients"],
                exclude_str = case["exclude_ingredients"]
            )
            found_titles = {r.title for r in results}
            end_time = time.time()
            latencies.append((end_time - start_time) * 1000)
            
            expected = set(case.get("should_contain", []))
            unwanted = set(case.get("should_not_contain", []))
            
            missing = expected - found_titles
            found_unwanted = found_titles.intersection(unwanted)
            
            if not missing and not found_unwanted:
                passed += 1
            else:
                # Extended log
                print(f" Filter testcase {case['id']} failed.")
                if missing: print(f"  - missing: {missing}")
                if found_unwanted: print(f"  - found unwanted: {found_unwanted}")
                
                # Or pass
                # pass
                
    accuracy = (passed / total) * 100
    avg_latency = mean(latencies)
    
    print(f"Filter accuracy: {accuracy:.2f}% ({passed}/{total} queries passed)")
    print(f"Average latency: {avg_latency:.5f} ms")
    print("----------------------------------------------------------------")

async def main():
    with open(NLS_QUIERIES_PATH) as f:
        nls_queries = json.load(f)
    with open(FILTER_QUERIES_PATH) as f:
        filter_queries = json.load(f)
    with open(RECIPES_PATH) as f:
        recipes = json.load(f)
        
    id_to_title = {r['id']: r['title'] for r in recipes}
    
    await evaluate_nls_method(
        "MySQL Full-Text Search",
        legacy_search_recipes,
        nls_queries,
        id_to_title
    )
    
    await evaluate_nls_method(
        "Vector search",
        recipe_service.search_recipes_by_vector,
        nls_queries,
        id_to_title
    )
    
    await evaluate_filters(
        "Naive String Matching (SQL Like operator)",
        legacy_get_all_recipes,
        filter_queries
    )
    
    await evaluate_filters(
        "Smart Word Boundary Filter",
        recipe_service.get_all_recipes,
        filter_queries
    )
    
if __name__ == "__main__":
    asyncio.run(main())