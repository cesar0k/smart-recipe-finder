from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any, AsyncGenerator

from db.session import AsyncSessionLocal
from schemas import Recipe, RecipeCreate, RecipeUpdate
from services import recipe_service

router = APIRouter()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/", response_model=Recipe, status_code=201)
async def create_new_recipe(*, db: AsyncSession = Depends(get_db), recipe_in: RecipeCreate) -> Any:
    return await recipe_service.create_recipe(db=db, recipe_in=recipe_in)

@router.get("/", response_model=List[Recipe])
async def read_recipes(
    *, 
    db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 100, 
    include_ingredients: str | None = Query(None, description="Comma-separated ingredient to include"),
    exclude_ingredients:str | None = Query(None, description="Comma-separated ingredient to exclude")
) -> Any:
    recipes = await recipe_service.get_all_recipes(
        db=db,
        skip=skip,
        limit=limit,
        include_str=include_ingredients,
        exclude_str=exclude_ingredients
    )
    return recipes

@router.get("/{recipe_id}", response_model=Recipe)
async def read_recipe_by_id(*, db: AsyncSession = Depends(get_db), recipe_id: int) -> Any:
    recipe = await recipe_service.get_recipe_by_id(db=db, recipe_id=recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe

@router.patch("/{recipe_id}", response_model=Recipe)
async def update_existing_recipe(*, db: AsyncSession = Depends(get_db), recipe_id: int, recipe_in: RecipeUpdate) -> Any:
    db_recipe = await recipe_service.get_recipe_by_id(db=db, recipe_id=recipe_id)
    if not db_recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    updated_recipe = await recipe_service.update_recipe(db=db, db_recipe=db_recipe, recipe_in=recipe_in)
    return updated_recipe

@router.delete("/{recipe_id}", response_model=Recipe)
async def delete_existing_recipe(*, db: AsyncSession = Depends(get_db), recipe_id: int) -> Any:
    deleted_recipe = await recipe_service.delete_recipe(db=db, recipe_id=recipe_id)
    if not deleted_recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    
    return deleted_recipe

@router.get(f"/search/", response_model=List[Recipe])
async def search_recipes(
    *,
    db: AsyncSession = Depends(get_db),
    q: str = Query(..., description="Search query for recipes using FTS")
) -> Any:
    return await recipe_service.search_recipes_by_fts(db=db, query_str=q)