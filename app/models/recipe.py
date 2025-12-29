from .base import Base

from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import JSONB


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), index=True, nullable=False)
    instructions = Column(String(50000), nullable=False)
    cooking_time_in_minutes = Column(Integer, nullable=False)
    difficulty = Column(String(50), nullable=False)
    cuisine = Column(String(50))
    ingredients = Column(JSONB, default=[], nullable=False)
