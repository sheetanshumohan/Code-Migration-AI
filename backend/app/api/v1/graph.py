"""
Graph Intelligence API Routes
Queries Neo4j for AST dependency graphs, call hierarchies, and blast radius calculations.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db, get_current_user
from app.infrastructure.database.neo4j.driver import neo4j_engine
from app.infrastructure.database.postgres.models import Project, Repository, User

router = APIRouter(prefix="/graph", tags=["Graph Intelligence"])


@router.get("/{repo_id}")
async def get_repository_graph(
    repo_id: str,
    limit: int = Query(250, ge=10, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """Fetch nodes and edges for React Flow interactive dependency graph."""
    import uuid
    try:
        parsed_repo_id = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository ID format.")

    stmt = select(Repository).join(Project).where(
        Repository.id == parsed_repo_id,
        Project.organization_id == current_user.organization_id
    )
    if not (await db.scalar(stmt)):
        raise HTTPException(status_code=403, detail="Access denied or repository not found")

    graph_data = await neo4j_engine.get_repository_graph_snapshot(repo_id, limit=limit)
    if not graph_data["nodes"]:
        return {"nodes": [], "edges": []}
    return graph_data


@router.get("/{repo_id}/blast-radius")
async def get_symbol_blast_radius(
    repo_id: str,
    symbol_name: str,
    file_path: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """Calculate the blast radius of modifying a specific function or class."""
    import uuid
    try:
        parsed_repo_id = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository ID format.")

    stmt = select(Repository).join(Project).where(
        Repository.id == parsed_repo_id,
        Project.organization_id == current_user.organization_id
    )
    if not (await db.scalar(stmt)):
        raise HTTPException(status_code=403, detail="Access denied or repository not found")

    records = await neo4j_engine.get_blast_radius(repo_id, symbol_name, file_path)
    return {
        "symbol_name": symbol_name,
        "file_path": file_path,
        "blast_radius_count": len(records),
        "impacted_callers": records,
    }
