from typing import Annotated, Any

from pydantic import Field, HttpUrl, StringConstraints, field_validator

from .ingredient import Ingredient
from .recipe_base import RecipeBase


class Recipe(RecipeBase):
    id: int
    ingredients: list[Ingredient] = Field(default_factory=list, max_length=100)
    image_urls: list[Annotated[HttpUrl, StringConstraints(max_length=1024)]] = Field(
        default_factory=list, max_length=10
    )

    @field_validator("image_urls", mode="before")
    def filter_empty_urls(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, list):
            return [url for url in v if url and isinstance(url, str) and url.strip()]
        return []

    # for reading data from SQLAlchemy objects
    class Config:
        from_attributes = True
