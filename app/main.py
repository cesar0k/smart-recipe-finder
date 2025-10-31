from fastapi import FastAPI
from contextlib import asynccontextmanager
from pydantic import BaseModel

from api.v1.api import api_router
from db.session import engine
from models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

class RootResponse(BaseModel):
    status: str
    project_name: str
    version: str
    documentation_url: str

app = FastAPI(
    title="Smart Recipes Finder", 
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/", response_model=RootResponse, tags=["Root"])
def read_root():
    return {
        "status": "ok",
        "project_name": app.title,
        "version": app.version,
        "documentation_url": "/docs"
    }
