"""
Sandbox Execution & Static Analysis API Routes
Executes linters, type checks, and tests within hermetic Docker sandboxes.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db, get_current_user
from app.infrastructure.database.postgres.models import Project, Repository, User
from app.infrastructure.repository_intel.git_engine import git_engine
from app.infrastructure.sandbox.docker_runner import docker_sandbox

router = APIRouter(prefix="/sandbox", tags=["Sandbox Validation"])


class RunValidationRequest(BaseModel):
    repository_id: str
    command: str = "pytest tests/ -v && ruff check ."
    timeout_seconds: int = 60


class ValidationResponse(BaseModel):
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


@router.post("/execute", response_model=ValidationResponse)
async def run_sandbox_validation(
    req: RunValidationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """Trigger a secure validation run in an isolated hermetic container."""
    import uuid
    try:
        parsed_repo_id = uuid.UUID(req.repository_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid repository ID format.")

    stmt = select(Repository).join(Project).where(
        Repository.id == parsed_repo_id,
        Project.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()

    if not repo:
        raise HTTPException(status_code=403, detail="Access denied or repository not found")

    repo_path = git_engine.get_repo_path(str(current_user.organization_id), req.repository_id)

    result = await docker_sandbox.execute_in_sandbox(
        workspace_dir=repo_path,
        command=req.command,
        timeout_seconds=req.timeout_seconds,
    )

    return ValidationResponse(
        passed=result.passed,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
    )
