from typing import Any, List, Optional, Sequence, Tuple, cast

import inflect
from sqlalchemy import not_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.selectable import Select

from app.core.s3_client import s3_client
from app.core.text_utils import get_word_forms
from app.core.vector_store import vector_store
from app.models import Recipe
from app.schemas import RecipeCreate, RecipeUpdate

p = inflect.engine()

__all__ = [
    "create_recipe",
    "get_all_recipes",
    "get_recipe_by_id",
    "update_recipe",
    "delete_recipe",
    "search_recipes_by_vector",
    "vector_store",
]


def _create_semantic_document(recipe: Recipe) -> tuple[str, dict[str, Any]]:
    time_description = "Standard cooking time"
    t = recipe.cooking_time_in_minutes
    if t <= 15:
        time_description = "Very quick, instant meal"
    elif t <= 30:
        time_description = "Quick, standard meal"
    elif t > 120:
        time_description = "Slow cooked, long preparation"

    ingredients_str = ""
    ingredients = cast(Any, recipe.ingredients)
    if ingredients:
        names = [item.get("name", "") for item in ingredients]
        ingredients_str = ", ".join(names)

    doc_to_embed = (
        f"Title: {recipe.title}. "
        f"Ingredients: {ingredients_str}. "
        f"Instructions: {recipe.instructions}. "
        f"Cooking time: {t} minutes ({time_description}). "
        f"Difficulty: {recipe.difficulty}. "
        f"Cuisine: {recipe.cuisine}."
    )

    metadata = {
        "title": recipe.title,
        "cooking_time": recipe.cooking_time_in_minutes,
        "difficulty": recipe.difficulty,
        "cuisine": recipe.cuisine or "",
    }

    return doc_to_embed, metadata


def _apply_ingredient_filter(
    query: Select[Tuple[Recipe]],
    include_str: Optional[str] = None,
    exclude_str: Optional[str] = None,
) -> Select[Tuple[Recipe]]:
    """
    Apply include/exclude filters to sqlalchemy object
    """
    if include_str:
        raw_items = [i.strip() for i in include_str.split(",") if i.strip()]
        for item in raw_items:
            terms = get_word_forms(item)

            or_condtitions = [Recipe.ingredients.contains([{"name": t}]) for t in terms]
            query = query.where(or_(*or_condtitions))

    if exclude_str:
        raw_items = [i.strip() for i in exclude_str.split(",") if i.strip()]
        exclude_conditions = []
        for item in raw_items:
            terms = get_word_forms(item)
            for t in terms:
                exclude_conditions.append(Recipe.ingredients.contains([{"name": t}]))

        if exclude_conditions:
            query = query.where(not_(or_(*exclude_conditions)))

    return query


async def create_recipe(db: AsyncSession, *, recipe_in: RecipeCreate) -> Recipe:
    recipe_data = recipe_in.model_dump(exclude={"ingredients"})
    json_ingredients = [{"name": name} for name in recipe_in.ingredients]

    db_recipe = Recipe(**recipe_data, ingredients=json_ingredients)

    db.add(db_recipe)
    await db.commit()
    await db.refresh(db_recipe)

    text, meta = _create_semantic_document(db_recipe)

    await vector_store.upsert_recipe(
        recipe_id=db_recipe.id,
        title=db_recipe.title,
        full_text=text,
        metadata=meta,
    )

    return db_recipe


async def get_all_recipes(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    include_str: Optional[str] = None,
    exclude_str: Optional[str] = None,
) -> Sequence[Recipe]:
    query = select(Recipe)

    query = _apply_ingredient_filter(query, include_str, exclude_str)

    query = query.order_by(Recipe.id.desc())
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_recipe_by_id(db: AsyncSession, *, recipe_id: int) -> Optional[Recipe]:
    query = select(Recipe).where(Recipe.id == recipe_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_recipe(
    db: AsyncSession, *, db_recipe: Recipe, recipe_in: RecipeUpdate
) -> Recipe:
    update_data = recipe_in.model_dump(exclude_unset=True)

    if "image_urls" in update_data:
        raw_urls = update_data.pop("image_urls")

        if raw_urls is None:
            new_urls_list = []
        else:
            new_urls_list = [str(url) for url in raw_urls]

        current_urls = set(db_recipe.image_urls) if db_recipe.image_urls else set()
        new_urls = set(new_urls_list)

        urls_to_delete = current_urls - new_urls

        db_recipe.image_urls = new_urls_list

        for url in urls_to_delete:
            await s3_client.delete_image_from_s3(url)

    if "ingredients" in update_data:
        raw_ingredients = update_data.pop("ingredients")
        json_ingredients = [{"name": i} for i in raw_ingredients]

        db_recipe.ingredients = json_ingredients

    if "image_urls" in update_data and update_data["image_urls"] is not None:
        update_data["image_urls"] = [str(url) for url in update_data["image_urls"]]

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
        metadata=meta,
    )

    return db_recipe


async def delete_recipe(db: AsyncSession, *, recipe_id: int) -> Optional[Recipe]:
    db_recipe = await get_recipe_by_id(db=db, recipe_id=recipe_id)
    if db_recipe:
        await db.delete(db_recipe)
        await db.commit()

        await vector_store.delete_recipe(recipe_id)
    return db_recipe


async def delete_recipe_images(
    db: AsyncSession, *, recipe_id: int, urls_to_delete: list[str]
) -> Recipe | None:
    db_recipe = await get_recipe_by_id(db=db, recipe_id=recipe_id)
    if not db_recipe:
        return None

    current_urls = set(db_recipe.image_urls) if db_recipe.image_urls else set()
    target_urls = set(urls_to_delete)

    urls_to_proccess = current_urls.intersection(target_urls)

    if not urls_to_proccess:
        return db_recipe

    remaining_urls = list(current_urls - urls_to_proccess)

    db_recipe.image_urls = remaining_urls
    db.add(db_recipe)
    await db.commit()
    await db.refresh(db_recipe)

    for url in urls_to_proccess:
        await s3_client.delete_image_from_s3(url)

    return db_recipe


async def search_recipes_by_vector(
    db: AsyncSession,
    *,
    query_str: str,
    include_str: Optional[str] = None,
    exclude_str: Optional[str] = None,
) -> List[Recipe]:
    recipe_ids = await vector_store.search(query=query_str, n_results=50)

    if not recipe_ids:
        return []

    query = select(Recipe).where(Recipe.id.in_(recipe_ids))

    query = _apply_ingredient_filter(query, include_str, exclude_str)

    result = await db.execute(query)
    recipes = result.scalars().unique().all()

    recipes_map = {r.id: r for r in recipes}
    ordered_recipes = []
    for rid in recipe_ids:
        if rid in recipes_map:
            ordered_recipes.append(recipes_map[rid])

    return ordered_recipes
