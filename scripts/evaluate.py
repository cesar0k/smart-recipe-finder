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
    
    accuracy, mrr, zrr = await evaluate_nls_method(
        "MySQL Full-Text Search",
        recipe_service.search_recipes_by_fts,
        nls_queries,
        id_to_title
    )
    
    await evaluate_filters(
        "Naive String Matching (SQL Like operator)",
        recipe_service.get_all_recipes,
        filter_queries
    )
    
if __name__ == "__main__":
    asyncio.run(main())