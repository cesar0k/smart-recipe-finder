from fastapi import FastAPI

from api.v1.api import api_router
from db.session import engine
from models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Recipes Finder")
app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to Smart Recipes Finder API!"}