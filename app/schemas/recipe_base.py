from pydantic import BaseModel

class RecipeBase(BaseModel):
    title: str
    ingredients: list[str] = []
    instructions: str
    cooking_time_in_minutes: int
    difficulty: str
    cuisine: str | None = None
