"""
Repository Management & Ingestion API Routes
Handles Git repository connections, synchronization, AST exploration, and file tree fetching.
"""

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RateLimiter, get_current_user
from app.core.security import encrypt_secret
from app.infrastructure.database.postgres.models import Project, Repository, User
from app.infrastructure.database.postgres.session import get_async_db
from app.infrastructure.repository_intel.git_engine import git_engine

router = APIRouter(prefix="/repositories", tags=["Repositories"])


class ConnectRepositoryRequest(BaseModel):
    name: str
    git_url: str
    default_branch: str = "main"
    auth_token: str | None = None

class ValidateRepositoryRequest(BaseModel):
    git_url: str
    auth_token: str | None = None


class RepositoryResponse(BaseModel):
    id: str
    name: str
    git_url: str
    default_branch: str
    sync_status: str
    detected_languages: list[str]
    detected_frameworks: list[str]
    ast_node_count: int


@router.get("", response_model=list[RepositoryResponse])
async def list_repositories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """List all repositories accessible to the user's organization."""
    stmt = (
        select(Repository)
        .join(Project)
        .where(Project.organization_id == current_user.organization_id)
    )
    result = await db.execute(stmt)
    repos = result.scalars().all()

    return [
        RepositoryResponse(
            id=str(r.id),
            name=r.name,
            git_url=r.git_url,
            default_branch=r.default_branch,
            sync_status=r.sync_status,
            detected_languages=r.detected_languages or [],
            detected_frameworks=r.detected_frameworks or [],
            ast_node_count=r.ast_node_count,
        )
        for r in repos
    ]


@router.post("/validate")
async def validate_repository_route(
    req: ValidateRepositoryRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Check if a remote git repository exists and is accessible."""
    from app.infrastructure.repository_intel.git_engine import git_engine
    is_valid = git_engine.validate_repository(req.git_url, req.auth_token)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Repository could not be accessed. Please verify the URL and ensure your Auth Token has the correct permissions."
        )
    return {"message": "Repository is valid and accessible."}

@router.post("/connect", response_model=RepositoryResponse, dependencies=[Depends(RateLimiter(requests=10, window=3600, scope="org"))])
async def connect_repository(
    req: ConnectRepositoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Connect a new Git repository and trigger initial clone & AST indexing."""
    # Ensure default project exists
    stmt = select(Project).where(Project.organization_id == current_user.organization_id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()

    if not project:
        project = Project(
            organization_id=current_user.organization_id,
            name="Default Modernization Project",
        )
        db.add(project)
        await db.flush()

    # Synchronous validation check
    from app.infrastructure.repository_intel.git_engine import git_engine
    is_valid = git_engine.validate_repository(req.git_url, req.auth_token)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Repository could not be accessed. Please verify the URL and ensure your Auth Token has the correct permissions."
        )

    encrypted_token = encrypt_secret(req.auth_token) if req.auth_token else None

    repo = Repository(
        project_id=project.id,
        name=req.name,
        git_url=req.git_url,
        default_branch=req.default_branch,
        encrypted_access_token=encrypted_token,
        sync_status="pending",
        detected_languages=[],
        detected_frameworks=[],
        ast_node_count=0,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    # Record cryptographic audit log
    from app.core.audit import record_audit_log
    await record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="create",
        resource_type="repository",
        resource_id=str(repo.id),
        metadata={
            "repo_name": repo.name,
            "git_url": repo.git_url,
            "default_branch": repo.default_branch,
        },
    )

    # Trigger Celery background indexing task
    from celery_app import index_repository_ast_task
    repo_path = git_engine.get_repo_path(str(current_user.organization_id), str(repo.id))
    index_repository_ast_task.delay(
        org_id=str(current_user.organization_id),
        repo_id=str(repo.id),
        repo_path=repo_path,
        repo_url=repo.git_url
    )

    return RepositoryResponse(
        id=str(repo.id),
        name=repo.name,
        git_url=repo.git_url,
        default_branch=repo.default_branch,
        sync_status=repo.sync_status,
        detected_languages=repo.detected_languages,
        detected_frameworks=repo.detected_frameworks,
        ast_node_count=repo.ast_node_count,
    )


@router.get("/{repo_id}/files")
async def get_repository_file_tree(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    # Enforce RBAC/IDOR: Check if the user's organization owns this repository
    import uuid
    try:
        parsed_repo_id = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository ID format.")

    stmt = (
        select(Repository)
        .join(Project)
        .where(
            Repository.id == parsed_repo_id,
            Project.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(status_code=403, detail="Repository not found or access denied.")

    repo_path = git_engine.get_repo_path(str(current_user.organization_id), repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found or not cloned yet.")

    files = await run_in_threadpool(git_engine.list_repository_files, repo_path)
    return [{"path": f, "type": "file"} for f in files]


@router.delete("/{repo_id}", status_code=204)
async def delete_repository_endpoint(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete a repository and all its associated data (AST, embeddings, files)."""
    import uuid
    try:
        parsed_repo_id = uuid.UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository ID format.")

    stmt = (
        select(Repository)
        .join(Project)
        .where(
            Repository.id == parsed_repo_id,
            Project.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(status_code=403, detail="Repository not found or access denied.")

    # 1. Delete graph data from Neo4j
    from app.infrastructure.database.neo4j.driver import neo4j_engine
    try:
        await neo4j_engine.delete_repository_ast(repo_id)
    except Exception:
        pass

    # 2. Delete vector embeddings from Qdrant
    from app.infrastructure.database.qdrant.client import qdrant_engine
    try:
        await qdrant_engine.delete_repository_embeddings(repo_id)
    except Exception:
        pass

    # 3. Delete files from disk
    from app.infrastructure.repository_intel.git_engine import git_engine
    try:
        await run_in_threadpool(git_engine.delete_repository, str(current_user.organization_id), repo_id)
    except Exception:
        pass

    # 4. Delete the Repository record from Postgres (cascades workflows, PRs, etc.)
    repo_name_saved = repo.name
    await db.delete(repo)
    await db.commit()

    # 5. Record audit log
    from app.core.audit import record_audit_log
    await record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="delete",
        resource_type="repository",
        resource_id=str(repo_id),
        metadata={
            "repo_name": repo_name_saved,
        },
    )
    await db.commit()
