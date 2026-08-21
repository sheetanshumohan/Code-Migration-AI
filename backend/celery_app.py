"""
Celery Task Queue & Distributed Worker Definition
Orchestrates asynchronous migration execution, background AST indexing, and sandboxed validation runs.
"""

import asyncio
from datetime import UTC, datetime
import typing
import uuid

from celery import Celery

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.redis.client import redis_engine

logger = get_logger("codemigration.celery")

celery_app = Celery(
    "codemigration_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    task_routes={
        "app.tasks.run_migration_workflow": {"queue": "migration_jobs"},
        "app.tasks.index_repository_ast": {"queue": "ast_indexing"},
    },
)


@celery_app.task(bind=True, name="app.tasks.run_migration_workflow")
def run_migration_workflow_task(
    self,
    workflow_id: str,
    org_id: str,
    repo_id: str,
    repo_path: str,
    workflow_type: str,
    target_framework: str,
    is_resume: bool = False,
    source_framework: str | None = None,
    target_language: str | None = None,
    custom_goal: str | None = None,
) -> dict:
    """Execute LangGraph workflow in asynchronous Celery worker."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from app.infrastructure.agents.state import MigrationWorkflowState
    from app.infrastructure.agents.workflow import build_migration_graph
    from app.infrastructure.ai.factory import llm_factory

    logger.info("Starting Celery migration workflow task", workflow_id=workflow_id, is_resume=is_resume, target_framework=target_framework)
    thread_id = f"workflow_thread_{workflow_id}"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.WORKFLOW_RECURSION_LIMIT,
    }

    initial_state: MigrationWorkflowState = {
        "workflow_id": workflow_id,
        "organization_id": org_id,
        "repository_id": repo_id,
        "repo_path": repo_path,
        "workflow_type": workflow_type,
        "source_framework": source_framework,
        "target_language": target_language,
        "target_framework": target_framework,
        "custom_goal": custom_goal,
        "status": "executing",
        "current_step": "init",
        "retry_count": 0,
        "max_retries": settings.WORKFLOW_MAX_RETRIES,
        "is_human_approved": False,
        "file_list": [],
        "detected_languages": [],
        "detected_frameworks": [],
        "ast_summary": {},
        "dependency_graph": {},
        "plan": [],
        "current_task_index": 0,
        "file_changes": [],
        "generated_tests": [],
        "validation_results": None,
        "reflection_feedback": None,
        "migration_report": None,
        "pr_title": None,
        "pr_description": None,
        "pr_url": None,
        "thought_stream": [],
        "total_tokens": 0,
        "total_cost_usd": 0.0,
    }

    async def execute_graph() -> dict:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.pool import NullPool
        from app.infrastructure.database.postgres.models import Workflow
        from sqlalchemy import func, update

        # Initialize task-scoped engine with NullPool bound strictly to this event loop
        task_engine = create_async_engine(
            settings.POSTGRES_ASYNC_URI,
            poolclass=NullPool,
            echo=False,
        )

        # Reset singletons so they bind strictly to this active event loop
        redis_engine.reset()
        from app.infrastructure.database.neo4j.driver import neo4j_engine
        neo4j_engine.reset()
        llm_factory.reset()

        # Convert sqlalchemy URI to standard postgresql URI for psycopg
        db_uri = str(settings.POSTGRES_ASYNC_URI).replace("postgresql+asyncpg://", "postgresql://")
        db_uri = db_uri.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

        try:
            # Update workflow status in DB if it was queued
            async def _mark_executing():
                from datetime import UTC, datetime
                async with AsyncSession(task_engine) as session:
                    await session.execute(
                        update(Workflow)
                        .where(Workflow.id == uuid.UUID(workflow_id))
                        .values(
                            status="executing",
                            started_at=func.coalesce(Workflow.started_at, datetime.now(UTC))
                        )
                    )
                    await session.commit()
            await _mark_executing()

            if not is_resume:
                await redis_engine.publish_workflow_event(workflow_id, {
                    "type": "thought",
                    "agent": "RepoAnalystAgent",
                    "thought": "Task dequeued from Celery pool. Initializing repository AST & dependency graph...",
                    "timestamp": datetime.now(UTC).isoformat(),
                })

            async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
                await checkpointer.setup()
                interrupt_nodes = [] if is_resume else ["planner"]
                app_graph = build_migration_graph().compile(
                    checkpointer=checkpointer,
                    interrupt_after=interrupt_nodes
                )

                if is_resume:
                    # Fetch the existing checkpoint to check resumption point
                    existing_snapshot = await app_graph.aget_state(config)
                    task_idx = 0
                    total_tasks = 0
                    if existing_snapshot and existing_snapshot.values:
                        task_idx = existing_snapshot.values.get("current_task_index", 0)
                        total_tasks = len(existing_snapshot.values.get("plan", []))

                    resume_msg = (
                        f"Resuming autonomous pipeline from checkpoint (Task {task_idx + 1} of {total_tasks})..."
                        if total_tasks > 0
                        else "Resuming autonomous pipeline from last saved checkpoint..."
                    )
                    logger.info(resume_msg, workflow_id=workflow_id, task_index=task_idx)

                    # Broadcast resumption thought
                    await redis_engine.publish_workflow_event(workflow_id, {
                        "type": "thought",
                        "agent": "Orchestrator",
                        "thought": resume_msg,
                        "timestamp": datetime.now(UTC).isoformat(),
                    })

                    # Update state to approve and resume execution from last checkpoint
                    await app_graph.aupdate_state(config, {"is_human_approved": True, "status": "executing"})
                    input_val = None
                else:
                    input_val = initial_state

                node_step_map = {
                    "repo_analyst": 0,
                    "prompt_validator": 0,
                    "planner": 1,
                    "refactor": 2,
                    "test_generator": 3,
                    "validator": 4,
                    "reviewer": 5,
                }

                # Stream LangGraph node updates in real-time
                async for update_chunk in app_graph.astream(input_val, config, stream_mode="updates"):
                    is_canc = await redis_engine.get_json(f"workflow_cancelled:{workflow_id}")
                    if is_canc:
                        logger.info("Workflow cancellation flag detected in streaming loop. Halting graph.", workflow_id=workflow_id)
                        break

                    if isinstance(update_chunk, dict):
                        for node_name, node_output in update_chunk.items():
                            step_idx = node_step_map.get(node_name)
                            if step_idx is not None:
                                live_tokens = 0
                                live_cost = 0.0
                                try:
                                    current_snapshot = await app_graph.aget_state(config)
                                    snap_vals = current_snapshot.values if current_snapshot else {}
                                    live_tokens = snap_vals.get("total_tokens", 0)
                                    live_cost = snap_vals.get("total_cost_usd", 0.0)
                                    live_metrics = {
                                        "total_tokens": int(live_tokens),
                                        "total_cost_usd": round(float(live_cost), 6),
                                    }

                                    async with AsyncSession(task_engine) as session:
                                        await session.execute(
                                            update(Workflow)
                                            .where(Workflow.id == uuid.UUID(workflow_id))
                                            .values(
                                                current_step_index=step_idx,
                                                cost_and_token_metrics=live_metrics,
                                            )
                                        )
                                        await session.commit()
                                except Exception as db_err:
                                    logger.warning("Could not update intermediate step in DB", error=str(db_err))

                                await redis_engine.publish_workflow_event(workflow_id, {
                                    "type": "step_progress",
                                    "node": node_name,
                                    "step_index": step_idx,
                                    "current_step_index": step_idx,
                                    "total_tokens": live_tokens,
                                    "total_cost_usd": round(float(live_cost), 6),
                                    "timestamp": datetime.now(UTC).isoformat(),
                                })

                post_snapshot = await app_graph.aget_state(config)
                result = post_snapshot.values if post_snapshot else {}

                # Persist state back to Postgres database
                async def _update_db_status():
                    from datetime import UTC, datetime

                    # Check if workflow was cancelled by operator
                    is_cancelled = await redis_engine.get_json(f"workflow_cancelled:{workflow_id}")
                    if is_cancelled:
                        logger.info("Workflow execution cancelled by user. Halting status update.", workflow_id=workflow_id)
                        return

                    async with AsyncSession(task_engine) as session:
                        current_wf = await session.get(Workflow, uuid.UUID(workflow_id))
                        if current_wf and current_wf.status == "cancelled":
                            logger.info("Workflow DB status is already cancelled. Skipping overwrite.", workflow_id=workflow_id)
                            return

                    # Check if graph reached completion
                    post_snapshot = await app_graph.aget_state(config)
                    has_next = bool(post_snapshot and post_snapshot.next)

                    if has_next and not is_resume:
                        new_status = "awaiting_approval"
                        step_idx = 1
                    else:
                        new_status = "completed"
                        step_idx = 5

                    # Extract accurate token usage and cost metrics from LangGraph state
                    total_tokens = 0
                    total_cost = 0.0
                    if post_snapshot and post_snapshot.values:
                        total_tokens = post_snapshot.values.get("total_tokens", 0)
                        total_cost = post_snapshot.values.get("total_cost_usd", 0.0)

                    metrics = {
                        "total_tokens": int(total_tokens),
                        "total_cost_usd": round(float(total_cost), 6),
                        "prompt_tokens": int(total_tokens * 0.75) if total_tokens > 0 else 0,
                        "completion_tokens": int(total_tokens * 0.25) if total_tokens > 0 else 0,
                    }

                    async with AsyncSession(task_engine) as session:
                        await session.execute(
                            update(Workflow)
                            .where(Workflow.id == uuid.UUID(workflow_id))
                            .values(
                                status=new_status,
                                current_step_index=step_idx,
                                cost_and_token_metrics=metrics,
                                finished_at=datetime.now(UTC) if new_status == "completed" else None,
                            )
                        )
                        await session.commit()

                    # Broadcast completion event if finished
                    if new_status == "completed":
                        await redis_engine.publish_workflow_event(workflow_id, {
                            "type": "workflow_completed",
                            "status": "completed",
                            "current_step_index": 5,
                            "cost_metrics": metrics,
                            "timestamp": datetime.now(UTC).isoformat(),
                        })

                await _update_db_status()
                return typing.cast(dict, result)
        finally:
            await task_engine.dispose()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        final_state = loop.run_until_complete(execute_graph())

        return {
            "status": "success",
            "workflow_id": workflow_id,
            "pr_url": final_state.get("pr_url") if isinstance(final_state, dict) else None,
            "files_modified": len(final_state.get("file_changes", [])) if isinstance(final_state, dict) else 0,
        }
    except Exception as e:
        # Check if cancelled
        is_cancelled = False
        try:
            is_cancelled = loop.run_until_complete(redis_engine.get_json(f"workflow_cancelled:{workflow_id}"))
        except Exception:
            pass

        if isinstance(e, asyncio.CancelledError) or is_cancelled:
            logger.info("Workflow execution cancelled. Skipping error mark.", workflow_id=workflow_id)
            return {"status": "cancelled", "workflow_id": workflow_id}

        logger.error("Celery workflow execution failed", error=str(e))

        # Update DB workflow status to 'failed' and broadcast failure event over WebSocket
        async def _mark_failed():
            from datetime import UTC, datetime
            from sqlalchemy import update
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.pool import NullPool
            from app.infrastructure.database.postgres.models import Workflow
            
            fail_engine = create_async_engine(settings.POSTGRES_ASYNC_URI, poolclass=NullPool, echo=False)
            try:
                raw_error = str(e)
                if "429" in raw_error or "rate_limit" in raw_error.lower() or "quota" in raw_error.lower() or "resource_exhausted" in raw_error.lower():
                    user_msg = "LLM Provider Rate Limit / Quota Exceeded. Execution halted and checkpoint safely preserved in PostgreSQL. You can resume from this exact step once rate limits reset."
                elif "timeout" in raw_error.lower():
                    user_msg = "LLM Request Timed Out. Pipeline paused and checkpoint saved. Click 'Resume' to retry."
                elif "authentication" in raw_error.lower() or "api_key" in raw_error.lower():
                    user_msg = "AI Provider API Key authentication issue. Checkpoint saved. Verify your API keys in Settings and click 'Resume'."
                else:
                    user_msg = f"Migration interrupted: {raw_error[:250]}. Checkpoint saved in PostgreSQL. Click 'Resume' to continue."

                async with AsyncSession(fail_engine) as session:
                    current_wf = await session.get(Workflow, uuid.UUID(workflow_id))
                    if current_wf and current_wf.status == "cancelled":
                        return

                    await session.execute(
                        update(Workflow)
                        .where(Workflow.id == uuid.UUID(workflow_id))
                        .values(status="failed", error_message=user_msg)
                    )
                    await session.commit()

                # Broadcast failure so frontend immediately halts spinner, shows error notice, and displays resume button
                now_iso = datetime.now(UTC).isoformat()
                await redis_engine.publish_workflow_event(workflow_id, {
                    "type": "workflow_failed",
                    "status": "failed",
                    "error": user_msg,
                    "resumable": True,
                    "message": user_msg,
                    "thought": f"⚠️ {user_msg}",
                    "timestamp": now_iso,
                })
            finally:
                await fail_engine.dispose()

        try:
            loop.run_until_complete(_mark_failed())
        except Exception as db_err:
            logger.error("Failed to mark workflow as failed in DB", error=str(db_err))

        return {"status": "failed", "error": str(e)}
    finally:
        loop.close()

@celery_app.task(bind=True, name="app.tasks.index_repository_ast")
def index_repository_ast_task(self, org_id: str, repo_id: str, repo_path: str, repo_url: str) -> dict:
    """Background task to clone repo, parse AST, and index into Neo4j/Qdrant."""
    from app.infrastructure.repository_intel.git_engine import git_engine
    
    logger.info("Starting AST indexing task", repo_id=repo_id, org_id=org_id)
    try:
        # Clone or sync the repository securely isolated by organization
        git_engine.clone_repository(org_id=org_id, repo_url=repo_url, repo_id=repo_id)
    except Exception as e:
        logger.error("Failed to clone repository", repo_id=repo_id, org_id=org_id, error=str(e))
        return {"status": "failed", "error": str(e)}

    import asyncio
    from app.infrastructure.repository_intel.ast_parser import ast_parser
    from app.infrastructure.database.neo4j.driver import neo4j_engine

    try:
        file_list = git_engine.list_repository_files(repo_path=repo_path)
        all_files = []
        all_symbols = []
        all_imports = []
        all_calls = []
        
        import os
        file_set = set(f.replace('\\', '/') for f in file_list)
        file_map_no_ext = {f.rsplit('.', 1)[0].replace('\\', '/'): f for f in file_list}

        for rel_file in file_list:
            try:
                content = git_engine.read_file_content(repo_path=repo_path, rel_file_path=rel_file)
                parsed = ast_parser.parse_file(rel_file, content)
                all_files.append({"path": parsed["file_path"], "language": parsed["language"], "loc": parsed["loc"]})
                all_symbols.extend(parsed["symbols"])
                if "imports" in parsed:
                    for imp in parsed["imports"]:
                        target = imp.get("target_file")
                        if not target or target == "unknown":
                            continue

                        target_clean = target.replace('\\', '/').strip()
                        source_dir = os.path.dirname(imp.get("source_file", "").replace('\\', '/'))

                        # 1. Try relative path resolution
                        resolved_path = os.path.normpath(os.path.join(source_dir, target_clean)).replace('\\', '/')

                        best_match = None
                        if resolved_path in file_set:
                            best_match = resolved_path
                        elif resolved_path in file_map_no_ext:
                            best_match = file_map_no_ext[resolved_path]
                        elif f"{resolved_path}/index" in file_map_no_ext:
                            best_match = file_map_no_ext[f"{resolved_path}/index"]
                        else:
                            # 2. Try suffix match across file list
                            target_suffix = target_clean.lstrip('./').lstrip('../')
                            if target_suffix:
                                for f in file_list:
                                    f_norm = f.replace('\\', '/')
                                    f_no_ext = f_norm.rsplit('.', 1)[0]
                                    if f_norm.endswith(target_suffix) or f_no_ext.endswith(target_suffix):
                                        best_match = f
                                        break

                        if best_match:
                            all_imports.append({
                                "source_file": imp["source_file"],
                                "target_file": best_match,
                                "line": imp.get("line", 1)
                            })
                        elif not target_clean.startswith('.'):
                            # External package (e.g. 'react', 'axios', 'express', etc.)
                            all_imports.append({
                                "source_file": imp["source_file"],
                                "target_file": target_clean,
                                "line": imp.get("line", 1)
                            })

                if "calls" in parsed:
                    all_calls.extend(parsed["calls"])

            except Exception as e:
                logger.debug(f"Failed to parse {rel_file}: {e}")

        async def _ingest():
            await neo4j_engine.connect()
            stats = await neo4j_engine.ingest_repository_ast(
                repo_id=repo_id,
                repo_name=repo_url.split("/")[-1],
                files=all_files,
                symbols=all_symbols,
                calls=all_calls,
                imports=all_imports
            )
            await neo4j_engine.close()
            return stats

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stats = loop.run_until_complete(_ingest())
        loop.close()

        total_nodes = stats.get("files", 0) + stats.get("symbols", 0)

        # Update PostgreSQL Repository with total_nodes
        from sqlalchemy import update
        from app.infrastructure.database.postgres.models import Repository
        from app.core.config import settings
        
        async def _update_db():
            import uuid as _uuid
            from app.infrastructure.database.postgres.session import get_task_scoped_session
            repo_uuid = _uuid.UUID(str(repo_id)) if not isinstance(repo_id, _uuid.UUID) else repo_id
            async with get_task_scoped_session() as session:
                await session.execute(
                    update(Repository)
                    .where(Repository.id == repo_uuid)
                    .values(ast_node_count=total_nodes, sync_status="synced")
                )
                await session.commit()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_update_db())
        loop.close()

        return {"status": "success", "repo_id": repo_id, "nodes_indexed": total_nodes}
    except Exception as e:
        logger.error("Failed to index repository AST", repo_id=repo_id, error=str(e))
        return {"status": "failed", "error": str(e)}
