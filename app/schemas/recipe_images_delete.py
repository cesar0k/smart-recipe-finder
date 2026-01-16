from typing import List

from pydantic import BaseModel, HttpUrl


class RecipeImagesDelete(BaseModel):
    image_urls: List[HttpUrl]
