"""
Planner Agent Node for LangGraph
Analyzes repository structure, dependencies, and migration targets to generate a Directed Acyclic Graph (DAG) plan.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.token_counter import calculate_cost, count_tokens
from app.infrastructure.agents.state import MigrationWorkflowState
from app.infrastructure.ai.factory import llm_factory
from app.infrastructure.database.redis.client import redis_engine

try:
    from langsmith import traceable
except ImportError:
    traceable = lambda *args, **kwargs: (lambda func: func) if (args and not callable(args[0])) else (args[0] if args else (lambda func: func))

logger = get_logger("codemigration.agent.planner")


class TaskItemSchema(BaseModel):
    id: str = Field(description="Unique task identifier, e.g., task_1")
    title: str = Field(description="Short descriptive title of the task")
    description: str = Field(description="Detailed explanation of the migration steps")
    target_files: list[str] = Field(description="List of file paths or directory paths to mutate in this task. Use directory paths for large codebases.")
    dependencies: list[str] = Field(description="List of task IDs that must complete before this one")

class PlanOutputSchema(BaseModel):
    summary: str = Field(description="High-level architectural migration strategy summary")
    tasks: list[TaskItemSchema] = Field(description="Ordered list of transformation tasks")


@traceable(name="PlannerNode", run_type="chain")
async def planner_node(state: MigrationWorkflowState) -> dict[str, Any]:
    """LangGraph node: Planner Agent decomposes the migration into discrete tasks."""
    is_cancelled = await redis_engine.get_json(f"workflow_cancelled:{state['workflow_id']}")
    if is_cancelled:
        logger.info("Workflow execution cancelled by user. Halting PlannerAgent.", workflow_id=state["workflow_id"])
        raise asyncio.CancelledError("Workflow was cancelled by operator.")

    logger.info("Executing Planner Agent", workflow_id=state["workflow_id"])

    # Stream real-time thought to WebSocket subscribers
    thought_event = {
        "agent": "PlannerAgent",
        "thought": f"Analyzing repository architecture to build DAG plan for {state['workflow_type']} -> {state.get('target_framework') or state.get('target_language')}...",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    await redis_engine.publish_workflow_event(state["workflow_id"], thought_event)

    from app.infrastructure.database.neo4j.driver import neo4j_engine
    graph_snapshot = await neo4j_engine.get_repository_graph_snapshot(state["repository_id"], limit=500)

    nodes = [n["id"] for n in graph_snapshot.get("nodes", [])]
    edges = [e["id"] for e in graph_snapshot.get("edges", [])]
    graph_context = f"Nodes: {nodes}\nDependencies: {edges}"

    # Extract all valid source code files discovered in the workspace
    all_files = state.get("file_list", [])
    ignored_exts = (
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot',
        '.lock', '.zip', '.tar', '.gz', '.min.js', '.map', '.bin', '.exe', '.md', '.txt',
        '.pdf', '.csv', '.json', '.yaml', '.yml', '.toml', '.xml', '.ini', '.cfg', '.env'
    )
    ignored_basenames = {
        'license', 'license.md', 'license.txt', 'readme.md', '.gitignore',
        '.eslintignore', '.prettierignore', '.npmignore', '.dockerignore',
        '.gitattributes', '.editorconfig', '.browserslistrc', 'package-lock.json',
        'yarn.lock', 'pnpm-lock.yaml', 'changelog.md', '_redirects', 'cname',
        'dockerfile', 'docker-compose.yml', 'docker-compose.yaml'
    }

    def _is_code_file(f: str) -> bool:
        base = f.replace('\\', '/').split('/')[-1].lower()
        if base.startswith('.'):
            return False
        if base in ignored_basenames or f.lower().endswith(ignored_exts):
            return False
        if any(part in f.replace('\\', '/').split('/') for part in ['.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv', 'venv']):
            return False
        return True

    source_files = [f for f in all_files if _is_code_file(f)]

    # If source_files is empty, fallback to non-hidden code files
    if not source_files and all_files:
        source_files = [f for f in all_files if not f.replace('\\', '/').split('/')[-1].startswith('.')] or all_files

    if len(source_files) > 40:
        module_groups: dict[str, list[str]] = {}
        for f in source_files:
            parts = f.replace('\\', '/').split('/')
            mod = parts[0] if len(parts) > 1 else 'root'
            module_groups.setdefault(mod, []).append(f)

        file_summary_lines = []
        for mod, mod_files in list(module_groups.items())[:15]:
            sample = ', '.join(mod_files[:5])
            file_summary_lines.append(f"  • Module [{mod}/] ({len(mod_files)} files): e.g. {sample}")
        files_representation = f"Total {len(source_files)} source files grouped across {len(module_groups)} architectural modules:\n" + "\n".join(file_summary_lines)
    else:
        files_representation = f"{source_files}"

    target_framework = state.get('target_framework') or 'Modern'
    target_language = state.get('target_language') or 'modern language standards'
    custom_goal = state.get('custom_goal') or 'Full modernization with 100% behavioral equivalence'

    prompt = f"""You are PlannerAgent, Principal Migration Architect.
Decompose the codebase migration into an ordered Directed Acyclic Graph (DAG) of atomic transformation tasks.

CONTEXT:
Workflow: {state['workflow_type']} | Source: {state.get('source_framework') or 'Legacy'} -> Target: {target_framework} ({target_language})
Target Framework: {target_framework}
Target Language: {target_language}
Goal: {custom_goal}
Source Files ({len(source_files)} total): {files_representation}
Graph Context: {graph_context}

RULES:
1. Partition the files into 3 to 10 logical tasks ordered by dependencies (e.g. Models/Config -> Services -> Controllers/Routes -> Tests).
2. Every target file in tasks MUST come from the source files list.
3. Dependencies must form a valid acyclic DAG.
4. Output structured JSON conforming to PlanOutputSchema.
"""

    llm = llm_factory.get_gateway()

    try:
        # LLM-generated plan
        response = await llm.generate_structured(
            system_prompt=prompt,
            user_prompt="Generate the optimal migration DAG plan.",
            response_model=PlanOutputSchema,
        )
        # Accurately compute token usage for structured planning
        prompt_tokens = count_tokens(prompt)
        comp_tokens = count_tokens(str(response.model_dump_json() if hasattr(response, "model_dump_json") else response.tasks))
        plan_tokens = prompt_tokens + comp_tokens
        provider_name = getattr(llm, "provider", "openai")
        plan_cost = calculate_cost(prompt_tokens, comp_tokens, provider=provider_name)

        tasks = [t.model_dump() for t in response.tasks]
        for task in tasks:
            task["status"] = "pending"

        state["status"] = "awaiting_approval"

    except Exception as e:
        logger.error(f"Planner LLM failed (likely token limit / max capacity): {e}")

        # Fallback: Construct a basic programmatic plan to ensure the workflow proceeds
        logger.info("Falling back to programmatic DAG plan generation.")

        fallback_tasks = []
        # Group files into chunks of 10 to ensure reasonable payload sizes
        chunk_size = 10
        chunks = [source_files[i:i + chunk_size] for i in range(0, len(source_files), chunk_size)]

        for idx, chunk in enumerate(chunks):
            fallback_tasks.append({
                "id": f"fallback_task_{idx+1}",
                "title": f"Migrate Batch {idx+1}",
                "description": f"Automatically generated task batch {idx+1} for robust execution after planning timeout or token limits.",
                "target_files": chunk,
                "dependencies": [f"fallback_task_{idx}"] if idx > 0 else [],
                "status": "pending"
            })

        if not fallback_tasks:
             fallback_tasks.append({
                "id": "fallback_task_1",
                "title": "Migrate Repository",
                "description": "Automatically generated generic task due to empty source files list.",
                "target_files": [],
                "dependencies": [],
                "status": "pending"
             })

        tasks = fallback_tasks
        prompt_tokens = count_tokens(prompt)
        comp_tokens = count_tokens(str(tasks))
        plan_tokens = prompt_tokens + comp_tokens
        provider_name = getattr(llm, "provider", "openai")
        plan_cost = calculate_cost(prompt_tokens, comp_tokens, provider=provider_name)
        state["status"] = "awaiting_approval"

        await redis_engine.publish_workflow_event(state["workflow_id"], {
            "agent": "PlannerAgent",
            "thought": "LLM hit output capacity. Generated modular fallback plan programmatically to guarantee completion.",
            "timestamp": datetime.now(UTC).isoformat(),
        })

    thought_event = {
        "agent": "PlannerAgent",
        "thought": f"Generated {len(tasks)} DAG migration milestones covering repository modules. Ready for execution.",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    event_type = "thought" if state.get("is_human_approved") else "plan_ready"
    await redis_engine.publish_workflow_event(state["workflow_id"], {
        "type": event_type,
        "agent": "PlannerAgent",
        "thought": thought_event["thought"],
        "tasks": tasks,
        "timestamp": thought_event["timestamp"],
    })

    return {
        "status": "awaiting_approval" if not state.get("is_human_approved") else "executing",
        "current_step": "PlannerAgent",
        "plan": tasks,
        "current_task_index": 0,
        "total_tokens": plan_tokens,
        "total_cost_usd": plan_cost,
        "thought_stream": [thought_event],
    }
