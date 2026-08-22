"""
Semantic Code Search & Repository Query API Routes
Vector search using Qdrant embeddings for finding functions, classes, and architectural concepts.
"""

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.infrastructure.database.postgres.models import Project, Repository, User
from app.infrastructure.database.postgres.session import get_async_db
from app.infrastructure.database.redis.client import redis_engine
from app.infrastructure.repository_intel.semantic_search import semantic_search_engine

router = APIRouter(prefix="/search", tags=["Semantic Search"])


class SearchResult(BaseModel):
    file_path: str
    symbol_name: str
    symbol_type: str
    language: str
    start_line: int
    end_line: int
    score: float
    code_snippet: str


@router.get("/{repo_id}", response_model=list[SearchResult])
async def search_repository_code(
    repo_id: str,
    q: str = Query(..., description="Natural language code search query"),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Execute vector semantic search across repository code chunks."""

    # 1. Enforce RBAC/IDOR (Performance & Security: Prevent unauthorized vector compute burn)
    import uuid
    try:
        parsed_repo_id = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository ID format.")

    stmt = select(Repository).join(Project).where(
        Repository.id == parsed_repo_id,
        Project.organization_id == current_user.organization_id
    )
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Repository not found or access denied.")

    # 2. Redis Caching layer
    cache_key = f"search:{repo_id}:{hashlib.sha256(q.encode()).hexdigest()}:{limit}"
    cached_results = await redis_engine.get_json(cache_key)
    if cached_results:
        return [SearchResult(**r) for r in cached_results]

    # 3. Expensive Vector Search
    results = await semantic_search_engine.search_code(repo_id, query=q, limit=limit)
    if not results:
        return []

    parsed_results = [
        SearchResult(
            file_path=r["payload"].get("file_path", "unknown"),
            symbol_name=r["payload"].get("symbol_name", "symbol"),
            symbol_type=r["payload"].get("symbol_type", "function"),
            language=r["payload"].get("language", "python"),
            start_line=r["payload"].get("start_line", 1),
            end_line=r["payload"].get("end_line", 1),
            score=r["score"],
            code_snippet=r["payload"].get("code_snippet", ""),
        )
        for r in results
    ]

    # Cache for 1 hour
    await redis_engine.set_json(cache_key, [r.model_dump() for r in parsed_results], ttl_seconds=3600)

    return parsed_results
