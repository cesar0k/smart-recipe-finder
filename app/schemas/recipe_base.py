from pydantic import BaseModel
from typing import Optional

class RecipeBase(BaseModel):
    title: str
    ingredients: str
    instructions: str
    cooking_time_in_minutes: int
    difficulty: str
    cuisine: Optional[str]
