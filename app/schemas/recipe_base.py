from typing import Optional

from pydantic import BaseModel, Field


class RecipeBase(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    instructions: Optional[str] = Field(None, max_length=50000)
    cooking_time_in_minutes: Optional[int] = None
    difficulty: Optional[str] = Field(None, max_length=50)
    cuisine: Optional[str] = Field(None, max_length=50)
