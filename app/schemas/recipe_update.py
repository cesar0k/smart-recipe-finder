from .recipe_base import RecipeBase


class RecipeUpdate(RecipeBase):
    title: str | None = None
    ingredients: list[str] | None = None
    instructions: str | None = None
    cooking_time_in_minutes: int | None = None
    difficulty: str | None = None
    cuisine: str | None = None
