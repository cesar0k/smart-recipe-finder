import asyncio
import json
import sys
import os
from pathlib import Path
from sqlalchemy import text, delete

sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal
from app.services import recipe_service
from app.schemas.recipe_create import RecipeCreate
from app.models.recipe import Recipe
from app.models.ingredient import Ingredient
from app.models.recipe_ingredient_association import recipe_ingredient_association

BASE_DIR = Path(__file__).parent.parent
RECIPES_PATH = BASE_DIR / "tests/datasets/recipe_samples.json"

async def seed():
    print("Seeding database...")
    
    async with AsyncSessionLocal() as db:
        print(" - Cleaning old data...")
        await db.execute(delete(recipe_ingredient_association))
        await db.execute(delete(Ingredient))
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