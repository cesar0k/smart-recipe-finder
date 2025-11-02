from .ingredient_base import IngredientBase

class Ingredient(IngredientBase):
    id: int
    
    class Config:
        from_attributes = True