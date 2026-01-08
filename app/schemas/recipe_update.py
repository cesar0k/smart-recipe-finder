from typing import Annotated, Optional

from pydantic import Field, HttpUrl, StringConstraints

from .recipe_base import RecipeBase


class RecipeUpdate(RecipeBase):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    ingredients: Optional[list[Annotated[str, StringConstraints(max_length=255)]]] = (
        Field(None, max_length=100)
    )
    instructions: Optional[str] = Field(None, max_length=50000)
    cooking_time_in_minutes: Optional[int] = None
    difficulty: Optional[str] = Field(None, max_length=50)
    cuisine: Optional[str] = Field(None, max_length=50)
    image_urls: Optional[
        list[Annotated[HttpUrl, StringConstraints(max_length=1024)]]
    ] = Field(None, max_length=10)
