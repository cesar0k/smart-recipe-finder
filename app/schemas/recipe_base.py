from pydantic import BaseModel, Field


class RecipeBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    instructions: str = Field(..., max_length=50000)
    cooking_time_in_minutes: int
    difficulty: str = Field(..., max_length=50)
    cuisine: str | None = Field(None, max_length=50)
