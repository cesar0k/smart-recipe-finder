from .base import Base

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(String(100), index=True, nullable=False)

    instructions = Column(Text, nullable=False)
    cooking_time_in_minutes = Column(Integer, nullable=False)
    difficulty = Column(String(50), nullable=False)
    cuisine = Column(String(50))

    ingredients_list = Column(ARRAY(String), default=[])

    @property
    def ingredients(self):
        return self.ingredients_list

    @ingredients.setter
    def ingredients(self, value):
        self.ingredients_list = value
