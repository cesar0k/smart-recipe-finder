from .base import Base
from .recipe_ingredient_association import recipe_ingredient_association

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(String(100), index=True, nullable=False)

    instructions = Column(Text, nullable=False)
    cooking_time_in_minutes = Column(Integer, nullable=False)
    difficulty = Column(String(50), nullable=False)
    cuisine = Column(String(50))

    ingredients = relationship(
        "Ingredient",
        secondary=recipe_ingredient_association,
        back_populates="recipes",
        lazy="selectin",
        order_by="Ingredient.id",
    )
