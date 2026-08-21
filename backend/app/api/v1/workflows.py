"""
Workflow & Migration Orchestration API Routes
Handles initiating migration DAGs, streaming status, pausing for human approval, and inspection.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_ai_rate_limit, get_current_user
from app.infrastructure.database.postgres.models import Project, Repository, User, Workflow
from app.infrastructure.database.postgres.session import get_async_db
from app.infrastructure.repository_intel.git_engine import git_engine

router = APIRouter(prefix="/workflows", tags=["Workflows & Migrations"])


class StartMigrationRequest(BaseModel):
    repository_id: str
    workflow_type: str = "framework_migration" # framework_migration, solid_refactor, security_remediation, state_management_migration, custom_modernization
    source_framework: str | None = None
    target_framework: str = "Modern Architecture"
    target_language: str = "same_as_source"
    custom_goal: str | None = None
    auto_approve: bool = False


class EnhancePromptRequest(BaseModel):
    source_framework: str | None = None
    target_framework: str | None = None
    target_language: str | None = None
    custom_goal: str


class EnhancedPromptOutput(BaseModel):
    enhanced_prompt: str = Field(..., description="The highly detailed, expanded architectural prompt.")


class WorkflowResponse(BaseModel):
    id: str
    repository_id: str
    repository_name: str | None = None
    workflow_type: str
    status: str
    target_framework: str | None
    current_step_index: int
    total_steps: int
    created_at: str
    error_message: str | None = None


@router.post("/start", response_model=WorkflowResponse, dependencies=[Depends(check_ai_rate_limit)])
async def start_migration_workflow(
    req: StartMigrationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Trigger an autonomous agent migration workflow."""
    from app.domain.migration.orchestrator import workflow_orchestrator

    try:
        workflow_record, repo_path = await workflow_orchestrator.initialize_workflow(
            db=db,
            current_user=current_user,
            repository_id=req.repository_id,
            workflow_type=req.workflow_type,
            target_framework=req.target_framework,
            target_language=req.target_language,
            auto_approve=req.auto_approve,
            source_framework=req.source_framework,
            custom_goal=req.custom_goal,
        )
    except ValueError as e:
        if str(e) == "Repository not found":
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=409, detail=str(e))

    workflow_id = str(workflow_record.id)

    # Record cryptographic audit log
    from app.core.audit import record_audit_log
    await record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="execute",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={
            "workflow_type": req.workflow_type,
            "source_framework": req.source_framework,
            "target_framework": req.target_framework,
            "target_language": req.target_language,
            "custom_goal": req.custom_goal,
            "repository_id": req.repository_id,
            "auto_approve": req.auto_approve,
        },
    )

    # Execute workflow in distributed Celery worker pool
    from celery_app import run_migration_workflow_task
    run_migration_workflow_task.delay(
        workflow_id=workflow_id,
        org_id=str(current_user.organization_id),
        repo_id=str(workflow_record.repository_id),
        repo_path=repo_path,
        workflow_type=req.workflow_type,
        target_framework=req.target_framework,
        source_framework=req.source_framework,
        target_language=req.target_language,
        custom_goal=req.custom_goal,
    )

    return WorkflowResponse(
        id=workflow_id,
        repository_id=str(workflow_record.repository_id),
        workflow_type=workflow_record.workflow_type,
        status=workflow_record.status,
        target_framework=workflow_record.target_framework,
        current_step_index=workflow_record.current_step_index,
        total_steps=workflow_record.total_steps,  # populated by orchestrator, not hardcoded
        created_at=str(workflow_record.created_at),
    )


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """List all workflows for the organization with repository names."""
    stmt = (
        select(Workflow, Repository.name.label("repo_name"))
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(Project.organization_id == current_user.organization_id)
        .order_by(Workflow.created_at.desc())
        .limit(50)
    )
    res = await db.execute(stmt)
    rows = res.all()

    return [
        WorkflowResponse(
            id=str(w.id),
            repository_id=str(w.repository_id),
            repository_name=repo_name or f"Repo {str(w.repository_id)[:6]}",
            workflow_type=w.workflow_type,
            status=w.status,
            target_framework=w.target_framework,
            current_step_index=w.current_step_index,
            total_steps=w.total_steps,
            created_at=str(w.created_at),
            error_message=w.error_message,
        )
        for w, repo_name in rows
    ]


@router.post("/enhance-prompt", response_model=dict, dependencies=[Depends(check_ai_rate_limit)])
async def enhance_prompt(
    req: EnhancePromptRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Uses LLM to expand a brief custom goal into a structured architectural constraint."""
    from app.core.config import settings
    from app.infrastructure.ai.factory import llm_factory

    if not req.custom_goal or len(req.custom_goal.strip()) == 0:
        raise HTTPException(status_code=400, detail="Custom goal cannot be empty.")

    prompt = f"""
    You are an Elite Enterprise Software Architect. A developer has submitted a brief, vague objective 
    for migrating or refactoring a codebase. Your task is to translate this vague objective into a highly 
    rigorous, structurally sound, and actionable architectural constraint prompt that will guide an 
    autonomous AI coding agent.

    CONTEXT:
    --------
    - Source Framework: {req.source_framework or 'Not specified'}
    - Target Framework: {req.target_framework or 'Not specified'}
    - Target Language: {req.target_language or 'Not specified'}
    - User's Vague Objective: "{req.custom_goal}"

    YOUR DIRECTIVE:
    ---------------
    Expand the user's objective into a comprehensive prompt by injecting best practices and strict technical constraints.
    Your output MUST explicitly cover the following dimensions (inferring appropriate modern standards where not explicitly provided by the user):

    1. Architectural Design & Patterns: Specify the structural pattern (e.g., Domain-Driven Design, Hexagonal Architecture, MVC, Microservices) and file organization principles.
    2. Data Flow & State Management: Define how state/data moves through the system, including API interaction contracts (REST/GraphQL/gRPC) and caching strategies.
    3. Dependencies & Tooling: Recommend industry-standard libraries for the target framework/language (e.g., ORMs, routing, UI components, validation) to prevent the agent from hallucinating outdated tools.
    4. Code Quality & Constraints: Enforce strict rules on typing (e.g., strict TypeScript, Python type hints), error handling, logging, and security (e.g., input sanitization).
    5. Migration Strategy (if applicable): Provide a tactical approach (e.g., incremental replacement, Strangler pattern) if moving between frameworks.

    OUTPUT FORMAT:
    --------------
    Produce ONLY the expanded, professional prompt. Do NOT include conversational filler, meta-commentary, or your reasoning. The output must be ready to be passed directly as the primary instruction to the execution agent.
    """

    gateway = llm_factory.get_gateway()
    try:
        response = await gateway.generate_text(
            system_prompt="You are a prompt engineering expert.",
            user_prompt=prompt,
            model=settings.DEFAULT_FAST_MODEL,
        )
        if response and response.content and len(response.content.strip()) > 20:
            return {"enhanced_prompt": response.content.strip()}
    except Exception as e:
        import logging
        logging.getLogger("codemigration.api.workflows").warning(f"AI Prompt enhancement failed, using architectural template: {e}")

    # Fallback to high-quality architectural specification
    src = req.source_framework or "Legacy Stack"
    tgt = req.target_framework or "Modern Architecture"
    lang = req.target_language or "Target Idiomatic Language"
    goal = req.custom_goal.strip()
    fallback_prompt = (
        f"Migrate and modernize this repository from {src} to {tgt} in {lang}.\n\n"
        f"### Primary Objectives & Requirements\n{goal}\n\n"
        f"### Architectural Constraints & Quality Gates\n"
        f"1. Modular Component Separation: Decouple business logic, state machines, and view layers following SOLID principles.\n"
        f"2. Strict Typing: Enforce strict type contracts with zero implicit 'any' types and comprehensive data interfaces.\n"
        f"3. Idiomatic Patterns: Replace deprecated lifecycle patterns with modern declarative APIs and idiomatic hooks.\n"
        f"4. Regression Test Synthesis: Guarantee 100% behavioral equivalence with unit and integration test coverage.\n"
        f"5. Error Handling & Security: Implement robust input sanitization and structured exception boundaries."
    )
    return {"enhanced_prompt": fallback_prompt}

@router.post("/{workflow_id}/approve")
async def approve_workflow_plan(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Human-in-the-loop: Approve the planned migration DAG to continue execution."""
    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Workflow.id == uuid.UUID(workflow_id),
            Project.organization_id == current_user.organization_id
        )
    )
    res = await db.execute(stmt)
    wf = res.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found or access denied")

    wf.status = "executing"
    await db.commit()

    # Record audit log
    from app.core.audit import record_audit_log
    await record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="approve",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={
            "workflow_type": wf.workflow_type,
            "target_framework": wf.target_framework,
            "event": "human_approved",
        },
    )

    # Broadcast approval event to WebSocket clients immediately
    from app.infrastructure.database.redis.client import redis_engine
    await redis_engine.publish_workflow_event(workflow_id, {
        "type": "plan_approved",
        "status": "executing",
        "agent": "PlannerAgent",
        "thought": "Migration plan approved by operator. Executing autonomous refactoring...",
        "timestamp": datetime.now(UTC).isoformat(),
    })

    # Trigger Celery worker to resume the LangGraph workflow
    from celery_app import run_migration_workflow_task
    repo_path = git_engine.get_repo_path(str(current_user.organization_id), str(wf.repository_id))

    run_migration_workflow_task.delay(
        workflow_id=workflow_id,
        org_id=str(current_user.organization_id),
        repo_id=str(wf.repository_id),
        repo_path=repo_path,
        workflow_type=wf.workflow_type,
        target_framework=wf.target_framework,
        is_resume=True,
    )

    return {"status": "approved", "workflow_id": workflow_id}


@router.post("/stop-all-active")
@router.post("/cancel-all")
async def stop_all_active_workflows(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Stop and cancel ALL active/executing workflows for the organization."""
    from datetime import UTC, datetime

    from app.infrastructure.database.redis.client import redis_engine

    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Project.organization_id == current_user.organization_id,
            Workflow.status.in_(["executing", "planning", "queued", "awaiting_approval", "validating"])
        )
    )
    res = await db.execute(stmt)
    active_wfs = res.scalars().all()

    stopped_ids = []
    for wf in active_wfs:
        wf.status = "cancelled"
        wf.finished_at = datetime.now(UTC)
        stopped_ids.append(str(wf.id))

        # Set Redis cancellation flag so background Celery worker halts immediately
        await redis_engine.set_json(f"workflow_cancelled:{wf.id}", True, ttl_seconds=86400)

        # Publish cancellation event
        await redis_engine.publish_workflow_event(str(wf.id), {
            "type": "error",
            "status": "cancelled",
            "agent": "Orchestrator",
            "message": "Workflow stopped by operator starting a new modernization.",
            "thought": "Workflow cancelled. Starting fresh modernization session.",
            "timestamp": datetime.now(UTC).isoformat(),
        })

    await db.commit()
    return {"status": "success", "stopped_workflow_ids": stopped_ids, "count": len(stopped_ids)}


@router.post("/{workflow_id}/cancel")
@router.post("/{workflow_id}/stop")
async def cancel_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Stop and cancel an active migration workflow execution."""
    from datetime import UTC, datetime

    from app.core.audit import record_audit_log
    from app.infrastructure.database.redis.client import redis_engine

    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Workflow.id == uuid.UUID(workflow_id),
            Project.organization_id == current_user.organization_id
        )
    )
    res = await db.execute(stmt)
    wf = res.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found or access denied")

    wf.status = "cancelled"
    wf.finished_at = datetime.now(UTC)
    await db.commit()

    # Set Redis cancellation flag so background Celery worker and LangGraph nodes halt immediately
    await redis_engine.set_json(f"workflow_cancelled:{workflow_id}", True, ttl_seconds=86400)

    # Publish real-time cancellation event to active WebSocket subscribers
    await redis_engine.publish_workflow_event(workflow_id, {
        "type": "error",
        "status": "cancelled",
        "agent": "Orchestrator",
        "current_step_index": wf.current_step_index or 0,
        "message": "Workflow execution was manually stopped by user.",
        "thought": "Workflow paused by operator. Checkpoint safely preserved.",
        "timestamp": datetime.now(UTC).isoformat(),
    })

    # Record audit trail
    await record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="cancel",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={
            "workflow_type": wf.workflow_type,
            "target_framework": wf.target_framework,
            "event": "user_cancelled",
        },
    )

    return {"status": "cancelled", "workflow_id": workflow_id}


@router.post("/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Resume a stopped, cancelled, failed, or interrupted workflow from its last saved LangGraph checkpoint."""
    from datetime import UTC, datetime

    from app.core.audit import record_audit_log
    from app.infrastructure.database.redis.client import redis_engine

    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Workflow.id == uuid.UUID(workflow_id),
            Project.organization_id == current_user.organization_id
        )
    )
    res = await db.execute(stmt)
    wf = res.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found or access denied")

    if wf.status == "completed":
        raise HTTPException(status_code=400, detail="This workflow is already completed.")

    # Ensure no other active workflow is currently running on the exact same repository
    stmt_active = (
        select(Workflow)
        .where(
            Workflow.repository_id == wf.repository_id,
            Workflow.id != wf.id,
            Workflow.status.in_(["planning", "executing", "validating"])
        )
    )
    active_res = await db.execute(stmt_active.limit(1))
    if active_res.first():
        raise HTTPException(
            status_code=409,
            detail="Another migration workflow is actively running on this repository. Please wait for it to complete."
        )

    wf.status = "executing"
    wf.error_message = None
    await db.commit()

    # Clear any previous cancellation flag in Redis
    await redis_engine.delete(f"workflow_cancelled:{workflow_id}")

    # Publish real-time resume event
    await redis_engine.publish_workflow_event(workflow_id, {
        "type": "workflow_resumed",
        "status": "executing",
        "agent": "Orchestrator",
        "current_step_index": wf.current_step_index or 0,
        "message": "Workflow execution resumed from last checkpoint.",
        "thought": "Resuming autonomous multi-agent pipeline from last saved checkpoint...",
        "timestamp": datetime.now(UTC).isoformat(),
    })

    # Record audit log
    await record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="resume",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={
            "workflow_type": wf.workflow_type,
            "target_framework": wf.target_framework,
            "event": "resumed_from_checkpoint",
        },
    )

    # Trigger Celery worker to resume LangGraph from checkpoint
    from celery_app import run_migration_workflow_task
    repo_path = git_engine.get_repo_path(str(current_user.organization_id), str(wf.repository_id))

    run_migration_workflow_task.delay(
        workflow_id=workflow_id,
        org_id=str(current_user.organization_id),
        repo_id=str(wf.repository_id),
        repo_path=repo_path,
        workflow_type=wf.workflow_type,
        target_framework=wf.target_framework,
        is_resume=True,
    )

    return {"status": "executing", "workflow_id": workflow_id, "resumed_from_checkpoint": True}


@router.get("/{workflow_id}")
async def get_workflow_details(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Get full workflow execution state, including agent thoughts and file diffs, leveraging LangGraph PostgreSQL checkpointer."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from app.core.config import settings
    from app.infrastructure.agents.workflow import build_migration_graph

    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Workflow.id == uuid.UUID(workflow_id),
            Project.organization_id == current_user.organization_id
        )
    )
    res = await db.execute(stmt)
    wf = res.scalar_one_or_none()

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Base response with DB metadata
    response_data: dict[str, Any] = {
        "id": str(wf.id),
        "repository_id": str(wf.repository_id),
        "workflow_type": wf.workflow_type,
        "status": wf.status,
        "target_framework": wf.target_framework,
        "target_language": wf.target_language,
        "current_step_index": wf.current_step_index,
        "total_steps": wf.total_steps,
        "created_at": str(wf.created_at),
        "started_at": str(wf.started_at) if wf.started_at else None,
        "finished_at": str(wf.finished_at) if wf.finished_at else None,
        "configuration": wf.configuration,
        "cost_and_token_metrics": wf.cost_and_token_metrics,
        "error_message": wf.error_message,
        "langgraph_state": None
    }

    # Retrieve LangGraph State directly from PostgreSQL checkpoints
    db_uri = str(settings.POSTGRES_ASYNC_URI).replace("postgresql+asyncpg://", "postgresql://")
    db_uri = db_uri.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")
    langgraph_state_dict: dict[str, Any] | None = None
    try:
        async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
            app_graph = build_migration_graph().compile(checkpointer=checkpointer)
            thread_id = wf.langgraph_thread_id
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": settings.WORKFLOW_RECURSION_LIMIT,
            }

            # Fetch state from checkpointer
            state = await app_graph.aget_state(config)
            if state and state.values:
                langgraph_state_dict = dict(state.values)
    except Exception as e:
        import logging
        logging.error(f"Failed to fetch LangGraph state for {workflow_id}: {str(e)}")

    # Also fetch Redis buffered events to guarantee 100% instant recovery on tab switching
    from app.infrastructure.database.redis.client import redis_engine
    buffered_events = await redis_engine.get_workflow_events(workflow_id)

    redis_thoughts = []
    redis_file_changes = []
    for ev in buffered_events:
        if ev.get("thought"):
            redis_thoughts.append({
                "agent": ev.get("agent", "Orchestrator"),
                "thought": ev.get("thought"),
                "timestamp": ev.get("timestamp"),
            })
        if ev.get("file_change"):
            redis_file_changes.append(ev.get("file_change"))
        elif ev.get("type") == "file_change" and ev.get("file_path"):
            redis_file_changes.append(ev)

    if langgraph_state_dict is None:
        langgraph_state_dict = {
            "thought_stream": redis_thoughts,
            "file_changes": redis_file_changes,
        }
    else:
        # If checkpointer thoughts are fewer than Redis buffered thoughts, merge
        # Merge thoughts deduplicating by thought content and agent
        existing_thoughts = list(langgraph_state_dict.get("thought_stream") or [])
        thought_keys = {(t.get("agent"), t.get("thought")) for t in existing_thoughts if isinstance(t, dict)}
        for rt in redis_thoughts:
            if isinstance(rt, dict) and (rt.get("agent"), rt.get("thought")) not in thought_keys:
                existing_thoughts.append(rt)
                thought_keys.add((rt.get("agent"), rt.get("thought")))
        langgraph_state_dict["thought_stream"] = existing_thoughts

        # Merge file changes deduplicating by file_path
        existing_changes = list(langgraph_state_dict.get("file_changes") or [])
        merged_changes_map = {fc["file_path"]: fc for fc in existing_changes if isinstance(fc, dict) and "file_path" in fc}
        for rfc in redis_file_changes:
            if isinstance(rfc, dict) and "file_path" in rfc:
                merged_changes_map[rfc["file_path"]] = rfc
        langgraph_state_dict["file_changes"] = list(merged_changes_map.values())

    response_data["langgraph_state"] = langgraph_state_dict

    # Accurately derive step index from latest event or status
    step_agent_map = {
        "RepoAnalystAgent": 0,
        "PlannerAgent": 1,
        "RefactorAgent": 2,
        "TestGenAgent": 3,
        "ValidationAgent": 4,
        "ReviewerAgent": 5,
    }
    latest_step_idx = wf.current_step_index
    if langgraph_state_dict and langgraph_state_dict.get("thought_stream"):
        latest_thought = langgraph_state_dict["thought_stream"][-1]
        agent_name = latest_thought.get("agent")
        if agent_name in step_agent_map:
            latest_step_idx = max(latest_step_idx, step_agent_map[agent_name])

    if wf.status == "completed":
        latest_step_idx = 5
    elif wf.status == "awaiting_approval":
        latest_step_idx = 1

    response_data["current_step_index"] = latest_step_idx

    return response_data

@router.post("/{workflow_id}/reject")
async def reject_workflow_plan(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Human-in-the-loop: Reject the planned migration DAG and halt execution."""
    from datetime import UTC, datetime

    from app.core.audit import record_audit_log
    from app.infrastructure.database.redis.client import redis_engine

    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Workflow.id == uuid.UUID(workflow_id),
            Project.organization_id == current_user.organization_id
        )
    )
    res = await db.execute(stmt)
    wf = res.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found or access denied")

    wf.status = "cancelled"
    wf.finished_at = datetime.now(UTC)
    await db.commit()

    # Set Redis cancellation flag so background Celery worker and LangGraph nodes halt immediately
    await redis_engine.set_json(f"workflow_cancelled:{workflow_id}", True, ttl_seconds=86400)

    # Broadcast rejection event
    await redis_engine.publish_workflow_event(workflow_id, {
        "type": "error",
        "status": "cancelled",
        "agent": "PlannerAgent",
        "message": "Migration plan was rejected by operator at human approval gate.",
        "thought": "Plan rejected by user. Pipeline halted safely.",
        "timestamp": datetime.now(UTC).isoformat(),
    })

    # Record audit log
    await record_audit_log(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="reject",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={
            "workflow_type": wf.workflow_type,
            "target_framework": wf.target_framework,
            "event": "human_rejected",
        },
    )

    return {"status": "rejected", "workflow_id": workflow_id}

@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """Delete a workflow history record."""
    stmt = (
        select(Workflow)
        .join(Repository, Workflow.repository_id == Repository.id)
        .join(Project, Repository.project_id == Project.id)
        .where(
            Workflow.id == uuid.UUID(workflow_id),
            Project.organization_id == current_user.organization_id
        )
    )
    res = await db.execute(stmt)
    wf = res.scalar_one_or_none()

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    await db.delete(wf)
    await db.commit()
    return {"status": "deleted"}
