from .recipe_base import RecipeBase
from .ingredient import Ingredient

class Recipe(RecipeBase):
    id: int
    ingredients_list: list[str] = []
    
    # for reading data from SQLAlchemy objects
    class Config:
        from_attributes = True