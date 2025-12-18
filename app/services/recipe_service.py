import inflect
from typing import Sequence, Any, List, cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import Recipe
from app.schemas import RecipeCreate, RecipeUpdate
from app.core.vector_store import vector_store

p = inflect.engine()

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

def _create_semantic_document(recipe: Recipe):
    time_description = "Standard cooking time"
    t = cast(int, recipe.cooking_time_in_minutes)
    if t <= 15:
        time_description = "Very quick, instant meal"
    elif t <= 30:
        time_description = "Quick, standard meal"
    elif t > 120:
        time_description = "Slow cooked, long preparation"
        
    ingredients_list = ", ".join(recipe.ingredients_list) if recipe.ingredients_list else ""
    
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
    ingredients_list = recipe_in.ingredients

    db_recipe = Recipe(**recipe_data, ingredients_list=ingredients_list)
    
    db.add(db_recipe)
    await db.commit()
    await db.refresh(db_recipe)
    
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
        raw_items = [i.strip() for i in include_str.split(',') if i.strip()]
        for item in raw_items:
            terms = list(_get_search_terms(item))
            
            query = query.where(Recipe.ingredients_list.overlap(terms))

    if exclude_str:
        raw_items = [i.strip() for i in exclude_str.split(',') if i.strip()]
        exclude_terms = []
        for item in raw_items:
            exclude_terms.extend(_get_search_terms(item))
            
        if exclude_terms:
            query = query.where(~Recipe.ingredients_list.overlap(exclude_terms))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_recipe_by_id(db: AsyncSession, *, recipe_id: int) -> Recipe | None:
    query = select(Recipe).where(Recipe.id == recipe_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def update_recipe(db: AsyncSession, *, db_recipe: Recipe, recipe_in: RecipeUpdate) -> Recipe:
    update_data = recipe_in.model_dump(exclude_unset=True)

    if "ingredients" in update_data:
        new_ingredients = update_data.pop("ingredients")
        db_recipe.ingredients_list = new_ingredients

    for field, value in update_data.items():
        setattr(db_recipe, field, value)

    db.add(db_recipe)
    await db.commit()
    
    await db.refresh(db_recipe)
    
    text, meta = _create_semantic_document(db_recipe)
    
    await vector_store.upsert_recipe(
        recipe_id=db_recipe.id,
        title=db_recipe.title,
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