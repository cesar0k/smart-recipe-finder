from typing import Annotated
from pydantic import Field, StringConstraints

from .recipe_base import RecipeBase


class RecipeUpdate(RecipeBase):
    title: str | None = Field(None, min_length=3, max_length=255)
    ingredients: list[Annotated[str, StringConstraints(max_length=255)]] | None = Field(None, max_items=100)
    instructions: str | None = Field(None, max_length=50000)
    cooking_time_in_minutes: int | None = None
    difficulty: str | None = Field(None, max_length=50)
    cuisine: str | None = Field(None, max_length=50)
