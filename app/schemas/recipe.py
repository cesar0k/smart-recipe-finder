from .recipe_base import RecipeBase

class Recipe(RecipeBase):
    id: int
    
    # for reading data from SQLAlchemy objects
    class Config:
        from_attributes = True