from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db, get_current_user
from app.infrastructure.database.postgres.models import (
    Project,
    PullRequest,
    Repository,
    User,
    Workflow,
)

router = APIRouter(prefix="/metrics", tags=["Metrics"])

@router.get("/kpi")
async def get_kpis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    # 1. Active workflows count (all actively running/planning/queued/awaiting states)
    active_workflows = await db.scalar(
        select(func.count(Workflow.id))
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
        .where(Workflow.status.in_(["executing", "queued", "planning", "awaiting_approval", "validating"]))
    ) or 0

    # 2. Total AST nodes indexed across all repos
    ast_nodes = await db.scalar(
        select(func.sum(Repository.ast_node_count))
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
    ) or 0

    # 3. Total completed migrations / generated PRs delivered
    completed_workflows = await db.scalar(
        select(func.count(Workflow.id))
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
        .where(Workflow.status == "completed")
    ) or 0

    total_prs = await db.scalar(
        select(func.count(PullRequest.id))
        .join(Workflow, PullRequest.workflow_id == Workflow.id)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
    ) or 0
    generated_prs = max(completed_workflows, total_prs)

    # 4. Total connected repositories
    total_repos = await db.scalar(
        select(func.count(Repository.id))
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
    ) or 0

    # 5. Sandbox security score & validation pass rate
    from app.infrastructure.database.postgres.models import ValidationRun
    total_validations = await db.scalar(
        select(func.count(ValidationRun.id))
        .join(Workflow, ValidationRun.workflow_id == Workflow.id)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
    ) or 0

    passed_validations = await db.scalar(
        select(func.count(ValidationRun.id))
        .join(Workflow, ValidationRun.workflow_id == Workflow.id)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Project.organization_id == current_user.organization_id,
            ValidationRun.passed.is_(True),
        )
    ) or 0

    sandbox_score = round((passed_validations / total_validations * 100), 1) if total_validations > 0 else (100.0 if completed_workflows > 0 else 100.0)

    # 6. Aggregate token consumption & cost across all workflows
    all_wf_stmt = (
        select(Workflow.cost_and_token_metrics)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
    )
    all_wf_res = await db.execute(all_wf_stmt)
    all_metrics = all_wf_res.scalars().all()

    total_tokens_sum = 0
    total_cost_sum = 0.0
    for m in all_metrics:
        if isinstance(m, dict):
            total_tokens_sum += m.get("total_tokens", 0)
            total_cost_sum += m.get("total_cost_usd", 0.0)

    return {
        "active_workflows": active_workflows,
        "ast_nodes": ast_nodes,
        "generated_prs": generated_prs,
        "total_repositories": total_repos,
        "total_tokens": total_tokens_sum,
        "total_cost_usd": round(total_cost_sum, 4),
        "sandbox_score": sandbox_score
    }

@router.get("/telemetry")
async def get_telemetry(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """Return time-series telemetry data aggregated from workflows for the active organization."""
    import datetime
    stmt = (
        select(
            Workflow.created_at,
            Workflow.started_at,
            Workflow.cost_and_token_metrics,
            Workflow.status,
            Workflow.target_framework,
            Repository.name
        )
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
        .order_by(Workflow.created_at.desc())
        .limit(min(max(limit, 1), 50))
    )
    result = await db.execute(stmt)
    workflows = result.fetchall()

    data = []
    for wf in reversed(workflows):
        created_at, started_at, metrics, status, target_fw, repo_name = wf
        metrics_dict = metrics if isinstance(metrics, dict) else {}
        tokens = metrics_dict.get("total_tokens", 0)
        cost = metrics_dict.get("total_cost_usd", 0.0)

        ts = started_at or created_at
        iso_str = None
        if ts:
            if ts.tzinfo is None:
                ts_utc = ts.replace(tzinfo=datetime.timezone.utc)
            else:
                ts_utc = ts
            iso_str = ts_utc.isoformat()

        data.append({
            "timestamp": iso_str,
            "time": ts.strftime("%b %d, %I:%M %p") if ts else "Recent",
            "time_short": ts.strftime("%I:%M %p") if ts else "00:00 AM",
            "tokens": tokens,
            "cost": round(cost, 4),
            "status": status,
            "target_framework": target_fw or "Modern Stack",
            "repo_name": repo_name or "Repository",
        })

    return data
