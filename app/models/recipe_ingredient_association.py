from sqlalchemy import Table, Column, Integer, ForeignKey
from .base import Base

recipe_ingredient_association = Table(
    "recipe_ingredient_association",
    Base.metadata,
    Column("recipe_id", Integer, ForeignKey("recipes.id"), primary_key=True),
    Column("ingredient_id", Integer, ForeignKey("ingredients.id"), primary_key=True),
)
