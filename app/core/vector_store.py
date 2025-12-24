import chromadb
import os
import sys
import logging
import asyncio
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "google/embeddinggemma-300m"


class VectorStore:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if kwargs.get("force_new", False):
            return super(VectorStore, cls).__new__(cls)
        if cls._instance is None:
            cls._instance = super(VectorStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, collection_name: str | None = None, force_new: bool = False):
        if getattr(self, "_initialized", False) and not force_new:
            return

        env_collection = os.getenv("CHROMA_COLLECTION_NAME")
        if collection_name:
            self.collection_name = collection_name
        elif env_collection:
            self.collection_name = env_collection
        else:
            self.collection_name = "recipes"

        try:
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST, port=settings.CHROMA_PORT
            )
        except Exception as ex:
            logger.error(f"Failed to connect to ChromaDB: {ex}")

        self.model = None

        self._initialized = True
        logger.info("Vector Store client initialized.")

    @property
    def collection(self):
        return self.client.get_or_create_collection(name=self.collection_name)

    def preload_model(self):
        if self.model is None:
            logger.info(f"Pre-load embedding model: {EMBEDDING_MODEL}...")
            self.model = SentenceTransformer(
                EMBEDDING_MODEL, trust_remote_code=True, token=settings.HF_TOKEN
            )
            logger.info(f"Embedding model pre-loaded successfully.")

    def _get_model(self) -> SentenceTransformer:
        if self.model is None:
            self.preload_model()

            if self.model is None:
                raise RuntimeError("Failed to load SentenceTransformer model.")
        return self.model

    async def embed_text(self, text: str) -> list[float]:
        model = self._get_model()
        embedding = await asyncio.to_thread(model.encode, text)
        return embedding.tolist()

    async def upsert_recipe(
        self, recipe_id: int, title: str, full_text: str, metadata: dict | None = None
    ):
        if metadata is None:
            metadata = {"title": title}
        safe_metadata = {k: ("" if v is None else v) for k, v in metadata.items()}

        embedding_result = await self.embed_text(full_text)

        def _sync_upsert():
            self.collection.upsert(
                ids=[str(recipe_id)],
                embeddings=[embedding_result],
                metadatas=[safe_metadata],
                documents=[full_text],
            )

        await asyncio.to_thread(_sync_upsert)

    async def search(self, query: str, n_results: int = 5) -> list[int]:
        query_vec_result = await self.embed_text(query)

        def _sync_search():
            return self.collection.query(
                query_embeddings=[query_vec_result], n_results=n_results
            )

        results = await asyncio.to_thread(_sync_search)

        if not results.get("ids") or not results["ids"][0]:
            return []

        return [int(id_str) for id_str in results["ids"][0]]

    async def delete_recipe(self, recipe_id: int):
        await asyncio.to_thread(self.collection.delete, ids=[str(recipe_id)])

    def clear(self):
        try:
            self.client.delete_collection(self.collection_name)
        except:
            pass
        self.client.get_or_create_collection(name=self.collection_name)


vector_store = VectorStore()
