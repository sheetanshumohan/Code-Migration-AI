import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.database.postgres.models import Project, Repository, User, Workflow
from app.infrastructure.repository_intel.git_engine import git_engine


class WorkflowOrchestrator:
    @staticmethod
    async def initialize_workflow(
        db: AsyncSession,
        current_user: User,
        repository_id: str,
        workflow_type: str,
        target_framework: str,
        target_language: str,
        auto_approve: bool,
        source_framework: str | None = None,
        custom_goal: str | None = None,
    ) -> tuple[Workflow, str]:
        """Validates concurrency, initializes state, and returns the Workflow model."""
        repo_uuid = uuid.UUID(repository_id)
        stmt = (
            select(Repository)
            .join(Project, Repository.project_id == Project.id)
            .where(
                Repository.id == repo_uuid,
                Project.organization_id == current_user.organization_id
            )
        )
        res = await db.execute(stmt)
        repo = res.scalar_one_or_none()

        if not repo:
            raise ValueError("Repository not found or access denied")

        # Concurrency constraint: Enforce single active migration workflow across the organization
        stmt_running = (
            select(Workflow)
            .join(Repository, Workflow.repository_id == Repository.id)
            .join(Project, Repository.project_id == Project.id)
            .where(
                Project.organization_id == current_user.organization_id,
                Workflow.status.in_(["planning", "executing", "awaiting_approval", "validating"])
            )
        )
        res_running = await db.execute(stmt_running.limit(1))
        if res_running.first():
            raise ValueError("A migration pipeline is already actively in progress. Please wait for it to complete or stop the running pipeline before starting another.")

        workflow_id = str(uuid.uuid4())
        thread_id = f"workflow_thread_{workflow_id}"

        workflow_record = Workflow(
            id=uuid.UUID(workflow_id),
            repository_id=repo.id,
            triggered_by_user_id=current_user.id,
            workflow_type=workflow_type,
            status="planning",
            target_framework=target_framework,
            target_language=target_language,
            configuration={
                "source_framework": source_framework,
                "target_framework": target_framework,
                "target_language": target_language,
                "custom_goal": custom_goal,
            },
            langgraph_thread_id=thread_id,
            total_steps=settings.WORKFLOW_TOTAL_STEPS,
        )
        db.add(workflow_record)
        await db.commit()

        repo_path = git_engine.get_repo_path(str(current_user.organization_id), str(repo.id))

        # This would optionally persist the initial state if using an external checkpoint
        # For now, Celery task builds it at runtime, but we guarantee the DB record is set.

        return workflow_record, repo_path

workflow_orchestrator = WorkflowOrchestrator()
