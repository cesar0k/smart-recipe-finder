from pydantic import Field

from .recipe_base import RecipeBase
from .ingredient import Ingredient


class Recipe(RecipeBase):
    id: int
    ingredients: list[Ingredient] = Field(default_factory=list, max_items=100)

    # for reading data from SQLAlchemy objects
    class Config:
        from_attributes = True
