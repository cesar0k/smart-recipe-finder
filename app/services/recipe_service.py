from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, or_

from typing import Sequence, cast, Any
import inflect

from app.models import Recipe, Ingredient
from app.schemas import RecipeCreate, RecipeUpdate

async def _get_or_create_ingredients(db: AsyncSession, ingredients_in: list[str]) -> Sequence[Ingredient]:
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

def _get_search_terms(raw_term: str) -> set[str]:
    term = raw_term.lower().strip()
    if not term:
        return set()
    
    terms = {term}
    
    singular = p.singular_noun(cast(Any, term))
    if singular:
        terms.add(singular)
        
    plural = p.plural(cast(Any, term))
    if plural:
        terms.add(plural)
        
    return terms

def _build_ingredient_filter(model_columm, term: str):
    return or_(
        model_columm == term,
        model_columm.like(f"{term} %"),
        model_columm.like(f"% {term}"),
        model_columm.like(f"% {term} %")
    )

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

p = inflect.engine()

async def get_all_recipes(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    include_str: str | None = None,
    exclude_str: str | None = None,
) -> Sequence[Recipe]:
    query = select(Recipe)

    if include_str:
        raw_includes = [item for item in include_str.split(",") if item.strip()]
        
        for raw_item in raw_includes:
            search_terms = _get_search_terms(raw_item)
            
            term_conditions = [
                _build_ingredient_filter(Ingredient.name, term)
                for term in search_terms
            ]
            
            query = query.where(Recipe.ingredients.any(or_(*term_conditions)))

    if exclude_str:
        raw_excludes = [item for item in exclude_str.split(',') if item.strip()]
        
        exclude_conditions = []
        for raw_item in raw_excludes:
            search_terms = _get_search_terms(raw_item)
            for term in search_terms:
                exclude_conditions.append(_build_ingredient_filter(Ingredient.name, term))
        
        if exclude_conditions:
            query = query.where(~Recipe.ingredients.any(or_(*exclude_conditions)))

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

async def search_recipes_by_fts(db: AsyncSession, *, query_str: str) -> Sequence[Recipe]:
    search_query = (
        select(Recipe).
        where(
            text("MATCH(title, instructions) AGAINST(:query IN NATURAL LANGUAGE MODE)")
        )
        .params(query=query_str)
    )
    
    result = await db.execute(search_query)
    
    return result.scalars().unique().all()