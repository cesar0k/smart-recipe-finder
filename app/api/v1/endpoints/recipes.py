from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any

from db.session import SessionLocal
from schemas import Recipe, RecipeCreate
from services import recipe_service

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=Recipe, status_code=201)
def create_new_recipe(*, db: Session = Depends(get_db), recipe_in: RecipeCreate) -> Any:
    return recipe_service.create_recipe(db=db, recipe_in=recipe_in)

@router.get("/", response_model=List[Recipe])
def read_recipes(*, db: Session = Depends(get_db), skip: int = 0, limit: int = 100) -> Any:
    return recipe_service.get_all_recipes(db=db, skip=skip, limit=limit)

@router.get("/{recipe_id}", response_model=Recipe)
def read_recipe_by_id(*, db: Session = Depends(get_db), recipe_id: int) -> Any:
    recipe = recipe_service.get_recipe_by_id(db=db, recipe_id=recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe
