import sys
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel

from app.api.v1.api import api_router
from app.core.vector_store import vector_store

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])


@asynccontextmanager
async def lifespan(app: FastAPI):
    vector_store.preload_model()
    yield


class RootResponse(BaseModel):
    status: str
    project_name: str
    version: str
    documentation_url: str


app = FastAPI(title="Smart Recipes Finder", version="1.1.0", lifespan=lifespan)

origins = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", response_model=RootResponse, tags=["Root"])
def read_root():
    return {
        "status": "ok",
        "project_name": app.title,
        "version": app.version,
        "documentation_url": "/docs",
    }
