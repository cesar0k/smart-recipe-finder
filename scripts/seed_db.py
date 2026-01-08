import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import delete

sys.path.append(os.getcwd())

from app.core.vector_store import vector_store
from app.db.session import AsyncSessionLocal
from app.models.recipe import Recipe
from app.schemas.recipe_create import RecipeCreate
from app.services import recipe_service

BASE_DIR = Path(__file__).parents[1]
RECIPES_PATH = BASE_DIR / "datasets" / "recipe_samples.json"


async def seed() -> None:
    print("Seeding database...")

    print("Cleaning Vector Store...")
    vector_store.clear()

    async with AsyncSessionLocal() as db:
        print(" - Cleaning old data...")
        await db.execute(delete(Recipe))
        await db.commit()

        print(" - Loading recipes...")
        with open(RECIPES_PATH) as f:
            recipes_data = json.load(f)

        for r_data in recipes_data:
            r_input = r_data.copy()
            if "id" in r_input:
                del r_input["id"]

            recipe_in = RecipeCreate(**r_input)
            await recipe_service.create_recipe(db=db, recipe_in=recipe_in)

        print(f"Successfully inserted {len(recipes_data)} recipes.")


if __name__ == "__main__":
    asyncio.run(seed())
