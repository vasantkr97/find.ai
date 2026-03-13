from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import aiofiles
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import VectorStoreError
from app.core.utils import chunk_text, generate_id
from app.services.llm import create_embedding, create_embeddings


class VectorDocument(BaseModel):
    id: str
    content: str
    embedding: list[float]
    metadata: dict[str, str]
    createdAt: int


class VectorSearchResult(BaseModel):
    document: VectorDocument
    score: float


class VectorStoreStats(BaseModel):
    totalDocuments: int
    sources: dict[str, int] = Field(default_factory=dict)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i, value in enumerate(a):
        b_val = b[i]
        dot += value * b_val
        norm_a += value * value
        norm_b += b_val * b_val
    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    return 0.0 if denom == 0 else dot / denom


class FileVectorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.documents: list[VectorDocument] = []
        self.loaded = False

    async def _ensure_loaded(self) -> None:
        if self.loaded:
            return
        try:
            async with aiofiles.open(self.path, encoding="utf-8") as fh:
                data = await fh.read()
            raw = json.loads(data)
            self.documents = [VectorDocument.model_validate(item) for item in raw]
        except FileNotFoundError:
            self.documents = []
        except Exception as err:  # noqa: BLE001
            raise VectorStoreError(f"Failed to load vector store: {err}") from err
        self.loaded = True

    async def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self.path, "w", encoding="utf-8") as fh:
            await fh.write(json.dumps([doc.model_dump() for doc in self.documents], ensure_ascii=True))

    async def add_documents(self, items: list[dict[str, Any]]) -> list[str]:
        await self._ensure_loaded()
        texts = [item["content"] for item in items]
        embeddings = await create_embeddings(texts)

        ids: list[str] = []
        for index, item in enumerate(items):
            doc = VectorDocument(
                id=generate_id(),
                content=item["content"],
                embedding=embeddings[index],
                metadata=item["metadata"],
                createdAt=item.get("createdAt", 0),
            )
            self.documents.append(doc)
            ids.append(doc.id)
        await self._persist()
        return ids

    async def ingest_text(
        self,
        text: str,
        metadata: dict[str, str],
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> int:
        cfg = get_settings()
        chunks = chunk_text(
            text,
            chunk_size or cfg.VECTOR_CHUNK_SIZE,
            overlap if overlap is not None else cfg.VECTOR_CHUNK_OVERLAP,
        )
        items = [{"content": c, "metadata": {**metadata, "chunkIndex": str(i)}} for i, c in enumerate(chunks)]
        await self.add_documents(items)
        return len(chunks)

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        threshold: float | None = None,
        metadata_filter: dict[str, str] | None = None,
    ) -> list[VectorSearchResult]:
        await self._ensure_loaded()
        if not self.documents:
            return []

        cfg = get_settings()
        top_k = top_k or cfg.VECTOR_DEFAULT_TOP_K
        threshold = cfg.VECTOR_SIMILARITY_THRESHOLD if threshold is None else threshold
        query_embedding = await create_embedding(query)

        candidates = self.documents
        if metadata_filter:
            candidates = [
                doc
                for doc in candidates
                if all(doc.metadata.get(k) == v for k, v in metadata_filter.items())
            ]

        scored = [
            VectorSearchResult(document=doc, score=_cosine_similarity(query_embedding, doc.embedding))
            for doc in candidates
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return [item for item in scored[:top_k] if item.score > threshold]

    async def has_documents_from_source(self, source_id: str) -> bool:
        await self._ensure_loaded()
        return any(doc.metadata.get("fileId") == source_id for doc in self.documents)

    async def delete_by_source(self, source_id: str) -> int:
        await self._ensure_loaded()
        before = len(self.documents)
        self.documents = [doc for doc in self.documents if doc.metadata.get("fileId") != source_id]
        deleted = before - len(self.documents)
        if deleted:
            await self._persist()
        return deleted

    async def get_stats(self) -> VectorStoreStats:
        await self._ensure_loaded()
        sources: dict[str, int] = {}
        for doc in self.documents:
            source = doc.metadata.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1
        return VectorStoreStats(totalDocuments=len(self.documents), sources=sources)


def _sanitize_user_id(user_id: str) -> str:
    if not user_id or any(ch for ch in user_id if not (ch.isalnum() or ch in {"_", "-"})):
        raise VectorStoreError("Invalid userId for vector store")
    return user_id


def get_store_path(user_id: str) -> Path:
    root = Path.cwd() / ".data" / "vectors"
    return root / f"{_sanitize_user_id(user_id)}.json"


def get_vector_store(user_id: str) -> FileVectorStore:
    return FileVectorStore(get_store_path(user_id))

