"""
Reports & Audit Logging API Routes
Fetches generated migration reports, test coverage metrics, and cryptographic audit trails.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.infrastructure.database.postgres.models import AuditLog, User, Workflow
from app.infrastructure.database.postgres.session import get_async_db

router = APIRouter(prefix="/reports", tags=["Reports & Audits"])


@router.get("/workflows")
async def list_workflow_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Retrieve summarized migration reports for all workflows in the organization."""
    from app.infrastructure.database.postgres.models import Project, Repository
    stmt = (
        select(Workflow, Repository.name.label("repo_name"))
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
        .order_by(Workflow.created_at.desc())
        .limit(50)
    )
    res = await db.execute(stmt)
    records = res.all()

    reports = []
    for wf, repo_name in records:
        metrics = wf.cost_and_token_metrics if isinstance(wf.cost_and_token_metrics, dict) else {}
        tokens = metrics.get("total_tokens", 0)
        cost = metrics.get("total_cost_usd", 0.0)

        reports.append({
            "workflow_id": str(wf.id),
            "repository_name": repo_name,
            "repository_id": str(wf.repository_id),
            "status": wf.status,
            "workflow_type": wf.workflow_type,
            "target_framework": wf.target_framework,
            "target_language": wf.target_language,
            "total_steps": wf.total_steps,
            "current_step_index": wf.current_step_index,
            "total_tokens": tokens,
            "total_cost_usd": round(cost, 4),
            "created_at": str(wf.created_at),
            "finished_at": str(wf.finished_at) if wf.finished_at else None,
            "error_message": wf.error_message,
        })

    return reports

@router.get("/workflows/{workflow_id}")
async def get_workflow_report(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Retrieve full migration report and validation metrics for a completed workflow."""
    from sqlalchemy.orm import selectinload

    from app.infrastructure.database.postgres.models import Project, Repository
    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .options(selectinload(Workflow.steps), selectinload(Workflow.validation_runs))
        .where(
            Workflow.id == uuid.UUID(workflow_id),
            Project.organization_id == current_user.organization_id
        )
    )
    res = await db.execute(stmt)
    wf = res.scalar_one_or_none()

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Build dynamic Markdown Report
    report_lines = [f"# Migration Report for Workflow {workflow_id}", f"\n**Status**: {wf.status}", f"**Target Framework**: {wf.target_framework}\n"]
    if wf.error_message:
        report_lines.append(f"## Errors\n{wf.error_message}\n")

    report_lines.append("## Execution Steps")
    if wf.steps:
        for step in wf.steps:
            report_lines.append(f"- **{step.step_name}** ({step.agent_role}): {step.status}")
    else:
        report_lines.append("No execution steps recorded.")

    report_lines.append("\n## Validation Runs")
    if wf.validation_runs:
        for run in wf.validation_runs:
            status_text = "PASSED" if run.passed else "FAILED"
            report_lines.append(f"- **{run.validation_type}**: {status_text} (Tests: {run.passed_tests}/{run.total_tests}, Coverage: {run.code_coverage_pct}%)")
    else:
        report_lines.append("No validation runs executed.")

    return {
        "workflow_id": str(wf.id),
        "status": wf.status,
        "workflow_type": wf.workflow_type,
        "target_framework": wf.target_framework,
        "cost_metrics": wf.cost_and_token_metrics,
        "report_markdown": "\n".join(report_lines),
    }


@router.get("/audit-logs")
async def get_audit_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Retrieve the immutable organization audit log trail."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == current_user.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(150)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    return [
        {
            "id": str(l.id),
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "ip_address": l.ip_address,
            "integrity_hash": l.integrity_hash,
            "created_at": str(l.created_at),
            "metadata": l.log_metadata or {},
        }
        for l in logs
    ]
