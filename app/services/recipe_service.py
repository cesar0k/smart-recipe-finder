from sqlalchemy.orm import Session
from sqlalchemy.future import select
from typing import List

from models import Recipe
from schemas import RecipeCreate

async def create_recipe(db: Session, *, recipe_in: RecipeCreate) -> Recipe:
    db_recipe = Recipe(**recipe_in.model_dump())
    db.add(db_recipe)
    await db.commit()
    await db.refresh(db_recipe)
    return db_recipe

async def get_all_recipes(db: Session, *, skip: int = 0, limit: int = 100) -> List[Recipe]:
    query = select(Recipe).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_recipe_by_id(db: Session, *, recipe_id: int) -> Recipe | None:
    query = select(Recipe).where(Recipe.id == recipe_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()
