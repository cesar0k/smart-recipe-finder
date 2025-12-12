import inflect
from typing import Sequence, Any, List, cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

from app.models import Recipe, Ingredient, recipe_ingredient_association
from app.schemas import RecipeCreate, RecipeUpdate
from app.core.vector_store import vector_store

p = inflect.engine()

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

def _create_semantic_document(recipe: Recipe):
    time_description = "Standard cooking time"
    t = cast(int, recipe.cooking_time_in_minutes)
    if t <= 15:
        time_description = "Very quick, instant meal"
    elif t <= 30:
        time_description = "Quick, standard meal"
    elif t > 120:
        time_description = "Slow cooked, long preparation"
        
    ingredients_list = ", ".join(i.name for i in recipe.ingredients)
    
    doc_to_embed = (
        f"Title: {recipe.title}. "
        f"Ingredients: {ingredients_list}. "
        f"Instructions: {recipe.instructions}. "
        f"Cooking time: {t} minutes ({time_description}). "
        f"Difficulty: {recipe.difficulty}. "
        f"Cuisine: {recipe.cuisine}."
    )
    
    metadata = {
        "title": recipe.title,
        "cooking_time": recipe.cooking_time_in_minutes,
        "difficulty": recipe.difficulty,
        "cuisine": recipe.cuisine or ""
    }
    
    return doc_to_embed, metadata

async def create_recipe(db: AsyncSession, *, recipe_in: RecipeCreate) -> Recipe:
    recipe_data = recipe_in.model_dump(exclude={"ingredients"})
    ingredient_names = recipe_in.ingredients

    db_recipe = Recipe(**recipe_data)
    db.add(db_recipe)

    await db.flush() 

    ingredient_objects = await _get_or_create_ingredients(db, ingredient_names)
    
    if ingredient_objects:
        rows_to_insert = [
            {"recipe_id": db_recipe.id, "ingredient_id": ing.id}
            for ing in ingredient_objects
        ]
        stmt = recipe_ingredient_association.insert().values(rows_to_insert)
        await db.execute(stmt)

    await db.commit()    
    
    await db.refresh(db_recipe)
    await db.refresh(db_recipe, attribute_names=["ingredients"])
    
    text, meta = _create_semantic_document(db_recipe)
    
    await vector_store.upsert_recipe(
        recipe_id=cast(int, db_recipe.id),
        title=cast(str, db_recipe.title),
        full_text=text,
        metadata=meta
    )
    
    return db_recipe

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

async def update_recipe(db: AsyncSession, *, db_recipe: Recipe, recipe_in: RecipeUpdate) -> Recipe:
    update_data = recipe_in.model_dump(exclude_unset=True)

    if "ingredients" in update_data:
        ingredient_names = update_data.pop("ingredients")
        ingredient_objects = await _get_or_create_ingredients(db, ingredient_names)
        
        delete_stmt = recipe_ingredient_association.delete().where(
            recipe_ingredient_association.c.recipe_id == db_recipe.id
        )
        await db.execute(delete_stmt)
        
        if ingredient_objects:
            rows_to_insert = [
                {"recipe_id": db_recipe.id, "ingredient_id": ing.id}
                for ing in ingredient_objects
            ]
            insert_stmt = recipe_ingredient_association.insert().values(rows_to_insert)
            await db.execute(insert_stmt)

    for field, value in update_data.items():
        setattr(db_recipe, field, value)

    db.add(db_recipe)
    await db.commit()
    
    await db.refresh(db_recipe)
    await db.refresh(db_recipe, attribute_names=["ingredients"])
    
    text, meta = _create_semantic_document(db_recipe)
    
    await vector_store.upsert_recipe(
        recipe_id=cast(int, db_recipe.id),
        title=cast(str, db_recipe.title),
        full_text=text,
        metadata=meta
    )
    
    return db_recipe

async def delete_recipe(db: AsyncSession, *, recipe_id: int) -> Recipe | None:
    db_recipe = await get_recipe_by_id(db=db, recipe_id=recipe_id)
    if db_recipe:
        await db.delete(db_recipe)
        await db.commit()
        
        await vector_store.delete_recipe(recipe_id)
    return db_recipe

async def search_recipes_by_vector(db: AsyncSession, *, query_str: str) -> List[Recipe]:
    recipe_ids = await vector_store.search(query=query_str, n_results=5)
    
    if not recipe_ids:
        return []
    
    query = select(Recipe).where(Recipe.id.in_(recipe_ids))
    result = await db.execute(query)
    recipes = result.scalars().unique().all()
    
    recipes_map = {cast(int, r.id): r for r in recipes}
    ordered_recipes = []
    for rid in recipe_ids:
        if rid in recipes_map:
            ordered_recipes.append(recipes_map[rid])
            
    return ordered_recipes