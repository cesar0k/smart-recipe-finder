import sys
import os
import time
import json
import asyncio
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Sequence
from statistics import mean

from alembic import command
from alembic.config import Config

from sqlalchemy import text, not_, or_, and_, func
from sqlalchemy.future import select
from sqlalchemy_utils import database_exists, create_database, drop_database
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal, AsyncSession
from app.services import recipe_service
from app.schemas.recipe_create import RecipeCreate
from app.models.recipe import Recipe
from tests.test_config import test_settings
from app.core.vector_store import VectorStore

import matplotlib
matplotlib.use("Agg")

TEST_COLLECTION_NAME = "recipes_test_collection"

BASE_PATH = Path(__file__).resolve().parent.parent
DATASETS_PATH = BASE_PATH / "datasets"

NLS_QUIERIES_PATH = DATASETS_PATH / "evaluation_nls_queries.json"
FILTER_QUERIES_PATH = DATASETS_PATH / "filter_test_data.json"
RECIPES_PATH = DATASETS_PATH / "recipe_samples.json"

LIMIT_TOP_K = 5

async def setup_test_db():
    print("Creating isolated database...")
    if database_exists(test_settings.SYNC_TEST_DATABASE_ADMIN_URL):
        drop_database(test_settings.SYNC_TEST_DATABASE_ADMIN_URL)
    create_database(test_settings.SYNC_TEST_DATABASE_ADMIN_URL)
    
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_settings.ASYNC_TEST_DATABASE_ADMIN_URL)
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

def teardown_test_db():
    print("Dropping isolated database...")
    if database_exists(test_settings.SYNC_TEST_DATABASE_ADMIN_URL):
        drop_database(test_settings.SYNC_TEST_DATABASE_ADMIN_URL)

async def seed_eval_data(session: AsyncSession):
    with open(RECIPES_PATH) as f:
        recipe_samples = json.load(f)

    print("Seeding recipes into test DB...")
    for r_data in recipe_samples:
        r_input = r_data.copy()
        if "id" in r_input: del r_input["id"]
        
        recipe_in = RecipeCreate(**r_input)
        
        await recipe_service.create_recipe(db=session, recipe_in=recipe_in)

def _build_array_string_filter(column_as_string, term: str):    
    return or_(
        column_as_string.ilike(f"% {term} %"),
        column_as_string.ilike(f"{term} %"),
        column_as_string.ilike(f"% {term}"),
        column_as_string == term
    )

async def legacy_smart_filter_on_array(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    include_str: str | None = None,
    exclude_str: str | None = None,
) -> Sequence[Recipe]:
    query = select(Recipe)

    array_as_string = func.array_to_string(Recipe.ingredients_list, ' ')
    
    if include_str:
        raw_includes = [item for item in include_str.split(',') if item.strip()]
        for item in raw_includes:
            search_terms = recipe_service._get_search_terms(item)
            
            term_conditions = [
                _build_array_string_filter(array_as_string, term)
                for term in search_terms
            ]
            
            query = query.where(or_(*term_conditions))

    if exclude_str:
        raw_excludes = [item for item in exclude_str.split(',') if item.strip()]
        exclude_conditions = []
        for item in raw_excludes:
            search_terms = recipe_service._get_search_terms(item)
            for term in search_terms:
                exclude_conditions.append(_build_array_string_filter(array_as_string, term))
        
        if exclude_conditions:
            query = query.where(not_(or_(*exclude_conditions)))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def evaluate_nls_method(db: AsyncSession, method_name, search_func, queries, id_to_title):
    print("------------------------------------------------------------------------")
    print(f"Evaluating '{method_name}', top {LIMIT_TOP_K} results are evaluated")
    
    passed = 0
    total = len(queries)
    latencies = []
    total_reciprocal_rank = 0.0
    zero_results_count = 0
    total_f1_score = 0.0
    
    category_stats = {}
    
    for q in queries:
        query_text = q['query']
        
        expected_ids = q.get('expected_ids')
        if expected_ids is None:
            expected_ids = [q['expected_id']] if 'expected_id' in q else []
        
        expected_titles = {id_to_title.get(eid) for eid in expected_ids if id_to_title.get(eid)}
        category = q.get("category", "unknown")
        
        if category not in category_stats:
            category_stats[category] = {"total": 0, "passed": 0, "total_f1": 0.0}
            
        start_time = time.time()
        results = await search_func(db=db, query_str=query_text)
        end_time = time.time()
        latencies.append((end_time - start_time) * 1000)

        results = results[:LIMIT_TOP_K]

        if not results:
            zero_results_count += 1
        
        found_titles = [r.title for r in results]
        found_titles_set = set(found_titles)
        
        intersection = expected_titles.intersection(found_titles_set)
        is_passed = len(intersection) > 0
        
        category_stats[category]["total"] += 1
        rank = 0
        if is_passed:
            for i, title in enumerate(found_titles):
                if title in expected_titles:
                    rank = i + 1
                    break
        if rank > 0:
            passed += 1
            category_stats[category]["passed"] += 1
            total_reciprocal_rank += 1.0 / rank
            
        relevant_retrieved = len(intersection)
        total_retrieved = len(found_titles)
        total_relevant_in_db = len(expected_titles)
        
        precision = (relevant_retrieved / total_retrieved) if total_retrieved > 0 else 0.0
        recall = (relevant_retrieved / total_relevant_in_db) if total_relevant_in_db > 0 else 0.0
        
        if (precision + recall) > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0.0
            
        total_f1_score += f1
        category_stats[category]["total_f1"] += f1
                
    accuracy = (passed / total) * 100
    avg_latency = mean(latencies)
    mean_reciprocal_rank = total_reciprocal_rank / total if total > 0 else 0.0
    zero_result_rate = (zero_results_count / total) * 100 if total > 0 else 0.0
    avg_f1_score = total_f1_score / total if total > 0 else 0.0
    
    print(f"By category:")
    for cat, stats in category_stats.items():
        cat_acc = (stats['passed'] / stats['total']) * 100
        cat_f1 = stats['total_f1'] / stats['total']
        print(f" - {cat:25}: {cat_acc:6.2f}% | F1: {cat_f1:.4f} ({stats['passed']}/{stats['total']})")
    print(f"Overall Accuracy: {accuracy}% ({passed}/{total})")
    print(f"Average latency: {avg_latency:.5f} ms")
    print(f"Mean Reciprocal Rank (MRR): {mean_reciprocal_rank:.5f}")
    print(f"Zero Result Rate (ZRR): {zero_result_rate:.2f}%")
    print(f"Average F1-Score: {avg_f1_score:.4f}")
    print("------------------------------------------------------------------------")
    
    return {
        "method": method_name,
        "accuracy": accuracy, 
        "mean_reciprocal_rank": mean_reciprocal_rank, 
        "zero_result_rate": zero_result_rate, 
        "avg_f1_score": avg_f1_score,
        "avg_latency": avg_latency
    }

async def evaluate_filters(method_name, filter_func, filter_queries):
    print("------------------------------------------------------------------------")
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
    print("------------------------------------------------------------------------")
    
    return {
        "method": method_name,
        "accuracy": accuracy,
        "avg_latency": avg_latency
    }

def plot_evaluation_results(nls_results, filter_results):
    print("\nGenerating evaluation charts...")
    
    plt.style.use('ggplot')
    
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(22, 6))
    fig.suptitle('Search & Filter evaluation results', fontsize=16)

    methods = [r['method'] for r in nls_results]
    accuracy = [r['accuracy'] for r in nls_results]
    f1 = [r['avg_f1_score'] * 100 for r in nls_results]
    mrr = [r['mean_reciprocal_rank'] * 100 for r in nls_results]
    zrr = [r['zero_result_rate'] for r in nls_results]

    x = np.arange(len(methods))
    width = 0.2

    ax1.bar(x - 1.5 * width, accuracy, width, label='Accuracy (%)', color='#3498db')
    ax1.bar(x - 0.5 * width, f1, width, label='F1-Score', color='#9b59b6')
    ax1.bar(x + 0.5 * width, mrr, width, label='MRR', color='#2ecc71')
    ax1.bar(x + 1.5 * width, zrr, width, label='Zero Result Rate (%)', color="#e14747")

    ax1.set_ylabel('Score')
    ax1.set_title('Search Quality')
    ax1.set_xticks(x)
    ax1.set_xticklabels(methods, rotation=15)
    ax1.legend()
    ax1.set_ylim(0, 110)

    for i, v in enumerate(accuracy):
        ax1.text(x[i] - 1.5 * width, v + 1.5, f"{v:.1f}%", ha='center', color='#3498db', fontsize=8)
    for i, v in enumerate(f1):
        ax1.text(x[i] - 0.5 * width, v + 1.5, f"{v/100:.4f}", ha='center', color='#9b59b6', fontsize=8)
    for i, v in enumerate(mrr):
        ax1.text(x[i] + 0.5 * width, v + 1.5, f"{v/100:.4f}", ha='center', color='#2ecc71', fontsize=8)
    for i, v in enumerate(zrr):
        ax1.text(x[i] + 1.5 * width, v + 1.5, f"{v:.1f}%", ha='center', color='#e14747', fontsize=8)

    f_methods = [r['method'] for r in filter_results]
    f_accuracy = [r['accuracy'] for r in filter_results]
    
    ax2.bar(f_methods, f_accuracy, color=['#e74c3c', '#27ae60'])
    ax2.set_title('Filter Accuracy')
    ax2.set_ylabel('Accuracy (%)')
    ax2.set_ylim(0, 110)
    for i, v in enumerate(f_accuracy):
        ax2.text(i, v + 1.5, f"{v:.1f}%", ha='center')

    all_methods = methods + f_methods
    all_latencies = [r['avg_latency'] for r in nls_results] + [r['avg_latency'] for r in filter_results]
    
    colors = ['#3498db'] * len(nls_results) + ['#e67e22'] * len(filter_results)
    
    ax3.bar(all_methods, all_latencies, color=colors)
    ax3.set_title('Average Latency (Log Scale)')
    ax3.set_ylabel('Time (ms)')
    ax3.set_yscale('log')
    ax3.set_xticklabels(all_methods, rotation=45, ha='right')
    
    output_path = "evaluation_results.png"
    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Charts saved to {output_path}")

async def main():
    await setup_test_db()
    
    eval_vector_store = VectorStore(collection_name=TEST_COLLECTION_NAME, force_new=True)
    original_vector_store = recipe_service.vector_store
    recipe_service.vector_store = eval_vector_store
    
    engine = create_async_engine(test_settings.ASYNC_TEST_DATABASE_ADMIN_URL)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    
    nls_results = []
    filter_results = []
    
    try:
        async with SessionLocal() as db:
            await seed_eval_data(db)
            
            with open(NLS_QUIERIES_PATH) as f:
                nls_queries = json.load(f)
            with open(FILTER_QUERIES_PATH) as f:
                filter_queries = json.load(f)
            with open(RECIPES_PATH) as f:
                recipes = json.load(f)
                
            id_to_title = {r['id']: r['title'] for r in recipes}
            
            vec_res = await evaluate_nls_method(
                db,
                "Vector search",
                recipe_service.search_recipes_by_vector,
                nls_queries,
                id_to_title
            )
            nls_results.append(vec_res)
            
            old_smart_fil_res = await evaluate_filters(
                "Adapted implementation of the old realization of Smart Word Boundary Filter",
                legacy_smart_filter_on_array,
                filter_queries
            )
            filter_results.append(old_smart_fil_res)
            
            overlap_smart_fil_res = await evaluate_filters(
                "New Fast Smart Word Boundary Filter (PostgreSQL overlap function with gin indexes)",
                recipe_service.get_all_recipes,
                filter_queries
            )
            filter_results.append(overlap_smart_fil_res)
            
            plot_evaluation_results(nls_results, filter_results)
    finally:
        print("Cleaning up...")
        await engine.dispose()
        recipe_service.vector_store = original_vector_store
        
        try:
            eval_vector_store.client.delete_collection(TEST_COLLECTION_NAME)
        except: 
            pass
        
        teardown_test_db()
        print("Cleaned up.")
    
if __name__ == "__main__":
    asyncio.run(main())