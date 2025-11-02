from pydantic import BaseModel

class IngredientBase(BaseModel):
    name: str