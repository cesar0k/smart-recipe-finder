from pydantic import BaseModel, HttpUrl


class RecipeImageDelete(BaseModel):
    image_url: HttpUrl
