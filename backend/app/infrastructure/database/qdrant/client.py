"""
Qdrant Vector Database Client for Code Intelligence & Semantic Search
Handles indexing code snippets, symbols, docstrings, and similarity retrieval.
"""

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("codemigration.db.qdrant")


class QdrantVectorEngine:
    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None
        self.vector_size: int = 1536 # Standard embedding dimension (e.g. OpenAI / text-embedding-3-small)

    async def connect(self) -> None:
        """Initialize connection to Qdrant Vector Engine."""
        try:
            self._client = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY,
                timeout=settings.QDRANT_TIMEOUT_SECONDS,
            )
            await self._init_collections()
            logger.info("Connected to Qdrant Vector Engine successfully")
        except Exception as e:
            logger.warning("Could not connect to Qdrant (will fallback or retry in live env)", error=str(e))

    async def close(self) -> None:
        """Close Qdrant client connection."""
        if self._client:
            await self._client.close()
            logger.info("Qdrant Vector Engine connection closed")

    async def _init_collections(self) -> None:
        """Create vector collections with HNSW indices if they do not exist."""
        if not self._client:
            return

        collections = [settings.QDRANT_COLLECTION_SYMBOLS, settings.QDRANT_COLLECTION_DOCS]
        for col in collections:
            exists = await self._client.collection_exists(col)
            if not exists:
                try:
                    await self._client.create_collection(
                        collection_name=col,
                        vectors_config=qmodels.VectorParams(
                            size=self.vector_size,
                            distance=qmodels.Distance.COSINE,
                        ),
                        hnsw_config=qmodels.HnswConfigDiff(
                            m=16,
                            ef_construct=128,
                        ),
                    )
                    logger.info("Created Qdrant collection", collection=col)
                except Exception as e:
                    if "409" in str(e) or "already exists" in str(e).lower():
                        logger.info("Qdrant collection already exists (handled worker race)", collection=col)
                    else:
                        raise e

            # Ensure payload indices exist for filtered fields on Qdrant Cloud
            for field_name in ["repo_id", "org_id", "language"]:
                try:
                    await self._client.create_payload_index(
                        collection_name=col,
                        field_name=field_name,
                        field_schema=qmodels.PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass

    async def upsert_code_symbols(
        self,
        repo_id: str,
        org_id: str,
        symbol_embeddings: list[dict[str, Any]],
    ) -> int:
        """Upsert a batch of code symbol vector points into Qdrant."""
        if not self._client or not symbol_embeddings:
            return 0

        points = []
        for s in symbol_embeddings:
            points.append(
                qmodels.PointStruct(
                    id=s["id"],
                    vector=s["vector"],
                    payload={
                        "repo_id": repo_id,
                        "org_id": org_id,
                        "file_path": s.get("file_path"),
                        "symbol_name": s.get("symbol_name"),
                        "symbol_type": s.get("symbol_type"),
                        "language": s.get("language"),
                        "code_snippet": s.get("code_snippet"),
                        "docstring": s.get("docstring"),
                    },
                )
            )

        await self._client.upsert(
            collection_name=settings.QDRANT_COLLECTION_SYMBOLS,
            points=points,
        )
        return len(points)

    async def search_symbols(
        self,
        repo_id: str,
        query_vector: list[float],
        limit: int = 10,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search code symbols by cosine similarity with metadata filters."""
        if not self._client:
            return []

        filter_conditions = [
            qmodels.FieldCondition(
                key="repo_id", match=qmodels.MatchValue(value=repo_id)
            )
        ]
        if language:
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="language", match=qmodels.MatchValue(value=language)
                )
            )

        try:
            results = await self._client.search(
                collection_name=settings.QDRANT_COLLECTION_SYMBOLS,
                query_vector=query_vector,
                query_filter=qmodels.Filter(must=filter_conditions),
                limit=limit,
            )
        except Exception as e:
            if "Index required" in str(e) or "index" in str(e).lower():
                try:
                    await self._client.create_payload_index(
                        collection_name=settings.QDRANT_COLLECTION_SYMBOLS,
                        field_name="repo_id",
                        field_schema=qmodels.PayloadSchemaType.KEYWORD,
                    )
                    results = await self._client.search(
                        collection_name=settings.QDRANT_COLLECTION_SYMBOLS,
                        query_vector=query_vector,
                        query_filter=qmodels.Filter(must=filter_conditions),
                        limit=limit,
                    )
                except Exception:
                    return []
            else:
                return []

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]

    async def upsert_code_embeddings(
        self,
        repo_id: str,
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> int:
        """Upsert raw code embeddings and payloads into Qdrant."""
        if not self._client or not vectors:
            return 0

        import uuid
        points = []
        for i, (vec, pld) in enumerate(zip(vectors, payloads, strict=False)):
            points.append(
                qmodels.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{repo_id}:{pld.get('file_path')}:{i}")),
                    vector=vec,
                    payload=pld,
                )
            )

        await self._client.upsert(
            collection_name=settings.QDRANT_COLLECTION_SYMBOLS,
            points=points,
        )
        return len(points)

    async def search_similar_code(
        self,
        repo_id: str,
        query_vector: list[float],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search code chunks by similarity vector."""
        return await self.search_symbols(repo_id=repo_id, query_vector=query_vector, limit=limit)

    async def delete_repository_embeddings(self, repo_id: str) -> None:
        """Delete all vector embeddings associated with a repository."""
        if not self._client:
            return

        filter_condition = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="repo_id", match=qmodels.MatchValue(value=repo_id)
                )
            ]
        )

        collections = [settings.QDRANT_COLLECTION_SYMBOLS, settings.QDRANT_COLLECTION_DOCS]
        for col in collections:
            try:
                await self._client.delete(
                    collection_name=col,
                    points_selector=qmodels.FilterSelector(filter=filter_condition)
                )
                logger.info(f"Deleted repository embeddings from {col}", repo_id=repo_id)
            except Exception as e:
                logger.error(f"Failed to delete repository embeddings from {col}", repo_id=repo_id, error=str(e))


qdrant_engine = QdrantVectorEngine()
