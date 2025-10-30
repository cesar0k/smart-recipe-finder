from sqlalchemy.orm import Session
from typing import List, Optional

from models import Recipe
from schemas import RecipeCreate

def create_recipe(db: Session, *, recipe_in: RecipeCreate) -> Recipe:
    db_recipe = Recipe(**recipe_in.model_dump())
    db.add(db_recipe)
    db.commit()
    db.refresh(db_recipe)
    return db_recipe

def get_all_recipes(db: Session, *, skip: int = 0, limit: int = 100) -> List[Recipe]:
    return db.query(Recipe).offset(skip).limit(limit).all()

def get_recipe_by_id(db: Session, *, recipe_id: int) -> Optional[Recipe]:
    return db.query(Recipe).filter(Recipe.id == recipe_id).first()
