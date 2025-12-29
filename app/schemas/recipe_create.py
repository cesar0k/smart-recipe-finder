from typing import Annotated
from pydantic import Field, StringConstraints

from .recipe_base import RecipeBase


class RecipeCreate(RecipeBase):
    ingredients: list[Annotated[str, StringConstraints(max_length=255)]] = Field(default_factory=list, max_items=100)
