from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from models import Recipe
from schemas import RecipeCreate, RecipeUpdate

async def create_recipe(db: AsyncSession, *, recipe_in: RecipeCreate) -> Recipe:
    db_recipe = Recipe(**recipe_in.model_dump())
    db.add(db_recipe)
    await db.commit()
    await db.refresh(db_recipe)
    return db_recipe

async def get_all_recipes(db: AsyncSession, *, skip: int = 0, limit: int = 100) -> List[Recipe]:
    query = select(Recipe).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_recipe_by_id(db: AsyncSession, *, recipe_id: int) -> Recipe | None:
    query = select(Recipe).where(Recipe.id == recipe_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def update_recipe(db: AsyncSession, *, db_recipe: Recipe, recipe_in: RecipeUpdate) -> Recipe:
    update_data = recipe_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_recipe, field, value)
        
    db.add(db_recipe)
    await db.commit()
    await db.refresh(db_recipe)
    return db_recipe

async def delete_recipe(db: AsyncSession, *, recipe_id: int) -> Recipe | None:
    db_recipe = await get_recipe_by_id(db=db, recipe_id=recipe_id)
    if db_recipe:
        await db.delete(db_recipe)
        await db.commit()
    return db_recipe