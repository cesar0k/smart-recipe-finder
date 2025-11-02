from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import not_

from typing import List

from models import Recipe, Ingredient
from schemas import RecipeCreate, RecipeUpdate


async def _get_or_create_ingredients(
    db: AsyncSession, ingredients_in: list[str]
) -> List[Ingredient]:
    ingredient_objects = []
    unique_ingredient_names = {name.lower().strip() for name in ingredients_in}

    for name in unique_ingredient_names:
        query = select(Ingredient).where(Ingredient.name == name)
        result = await db.execute(query)
        ingredient = result.scalar_one_or_none()

        if not ingredient:
            ingredient = Ingredient(name=name)
            db.add(ingredient)
            await db.flush()

        ingredient_objects.append(ingredient)

    return ingredient_objects


async def create_recipe(db: AsyncSession, *, recipe_in: RecipeCreate) -> Recipe:
    recipe_data = recipe_in.model_dump(exclude={"ingredients"})
    ingredient_names = recipe_in.ingredients

    db_recipe = Recipe(**recipe_data)
    db.add(db_recipe)
    await db.commit()
    await db.refresh(db_recipe)

    ingredient_objects = await _get_or_create_ingredients(db, ingredient_names)
    db_recipe.ingredients = ingredient_objects
    await db.commit()    
    await db.refresh(db_recipe, attribute_names=["ingredients"])
    return db_recipe


async def get_all_recipes(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    include_str: str | None = None,
    exclude_str: str | None = None,
) -> List[Recipe]:
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


async def get_recipe_by_id(db: AsyncSession, *, recipe_id: int) -> Recipe | None:
    query = select(Recipe).where(Recipe.id == recipe_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_recipe(
    db: AsyncSession, *, db_recipe: Recipe, recipe_in: RecipeUpdate
) -> Recipe:
    update_data = recipe_in.model_dump(exclude_unset=True)

    if "ingredients" in update_data:
        ingredient_names = update_data.pop("ingredients")
        ingredient_objects = await _get_or_create_ingredients(db, ingredient_names)
        db_recipe.ingredients = ingredient_objects


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
