from .base import Base
from .recipe_ingredient_association import recipe_ingredient_association

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

class Ingredient(Base):
    __tablename__ = "ingredients"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    
    recipes = relationship(
        "Recipe",
        secondary=recipe_ingredient_association,
        back_populates="ingredients"
    )