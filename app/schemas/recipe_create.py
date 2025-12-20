from .recipe_base import RecipeBase

class RecipeCreate(RecipeBase):
    ingredients: list[str] = []