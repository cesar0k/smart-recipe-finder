import sys
import os
import time
import json
import asyncio
from pathlib import Path
from statistics import mean

sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.services import recipe_service

BASE_PATH = Path(__file__).parent.parent
NLS_QUIERIES_PATH = BASE_PATH / "tests/datasets/evaluation_nls_queries.json"
FILTER_QUERIES_PATH = BASE_PATH / "tests/datasets/filter_test_data.json"
RECIPES_PATH = BASE_PATH / "tests/datasets/recipe_samples.json"

async def evaluate_nls_method(method_name, search_func, queries, id_to_title):
    print(f"Evaluating '{method_name}'")
    
    hits = 0
    total = len(queries)
    latencies = []
    
    category_stats = {}
    
    async with AsyncSessionLocal() as db:
        for q in queries:
            query_text = q['query']
            expected_id = q['expected_id']
            expected_title = id_to_title.get(expected_id)
            category = q.get("category", "unknown")
            
            if category not in category_stats:
                category_stats[category] = {"total": 0, "hits": 0}
                
            start_time = time.time()
            results = await search_func(db=db, query_str=query_text)
            found_titles = [r.title for r in results]
            end_time = time.time()
            latencies.append((end_time - start_time) * 1000)
            
            is_hit = expected_title in found_titles
            category_stats[category]["total"] += 1
            if is_hit:
                hits += 1
                category_stats[category]["hits"] += 1
            else:
                pass
                # print(f"Missed: '{query_text}', category: {category}, found titles: {found_titles}")
                
    accuracy = (hits / total) * 100
    avg_latency = mean(latencies)
    
    print(f"By Category:")
    for cat, stats in category_stats.items():
        cat_acc = (stats['hits'] / stats['total']) * 100
        print(f" - {cat}: {cat_acc:.2f}% ({stats['hits']} / {stats['total']})")
    print(f"Overall Accuracy: {accuracy}% ({hits}/{total})")
    print(f"Average latency: {avg_latency:.5f} ms")
    
    return accuracy

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
        recipe_service.search_recipes_by_fts,
        nls_queries,
        id_to_title
    )
    
if __name__ == "__main__":
    asyncio.run(main())