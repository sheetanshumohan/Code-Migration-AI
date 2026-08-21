"""
Test Generation Agent Node for LangGraph
Synthesizes comprehensive unit, integration, and regression test suites for newly transformed code.
"""

import asyncio
import os
import re
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.core.token_counter import calculate_cost, count_tokens
from app.infrastructure.agents.state import MigrationWorkflowState
from app.infrastructure.ai.factory import llm_factory
from app.infrastructure.database.redis.client import redis_engine
from app.infrastructure.repository_intel.git_engine import git_engine

try:
    from langsmith import traceable
except ImportError:
    traceable = lambda *args, **kwargs: (lambda func: func) if (args and not callable(args[0])) else (args[0] if args else (lambda func: func))

logger = get_logger("codemigration.agent.testgen")


@traceable(name="TestGeneratorNode", run_type="chain")
async def test_generator_node(state: MigrationWorkflowState) -> dict[str, Any]:
    """LangGraph node: Generates automated regression tests for transformed files."""
    is_cancelled = await redis_engine.get_json(f"workflow_cancelled:{state['workflow_id']}")
    if is_cancelled:
        logger.info("Workflow execution cancelled by user. Halting TestGenAgent.", workflow_id=state["workflow_id"])
        raise asyncio.CancelledError("Workflow was cancelled by operator.")

    logger.info("Executing Test Generation Agent", workflow_id=state["workflow_id"])

    await redis_engine.publish_workflow_event(state["workflow_id"], {
        "agent": "TestGenAgent",
        "thought": "Synthesizing comprehensive regression test suites for transformed modules...",
        "timestamp": datetime.now(UTC).isoformat(),
    })

    file_changes = state.get("file_changes", [])
    generated_tests: list[dict[str, str]] = []
    llm = llm_factory.get_gateway()

    step_tokens = 0
    step_cost = 0.0

    task_idx = state.get("current_task_index", 0)
    plan = state.get("plan", [])
    current_task = plan[task_idx] if task_idx < len(plan) else None
    target_files = current_task["target_files"] if current_task else []

    # Process only the files modified in the current DAG task
    valid_code_exts = ('.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.cs', '.rb', '.php')
    recent_changes = [
        c for c in file_changes
        if any(c.get("file_path", "").lower().endswith(ext) for ext in valid_code_exts)
        and not os.path.basename(c.get("file_path", "")).startswith('.')
        and (
            not target_files or any(
                c["file_path"].replace('\\', '/').startswith(tf.replace('\\', '/').rstrip('/') + '/')
                or c["file_path"].replace('\\', '/') == tf.replace('\\', '/')
                for tf in target_files
            )
        )
    ]

    for change in recent_changes:
        file_path = change["file_path"]
        code = change["transformed_code"]
        if len(code) > 8000:
            code = "\n".join(code.splitlines()[:200])

        system_prompt = """You are TestGenAgent, Principal Test Automation Engineer.
Generate isolated unit tests (pytest for Python, vitest/jest for JS/TS) for the provided modernized code module.
RULES:
1. Mock all external I/O (database, network/HTTP, filesystem).
2. Cover happy paths and key error cases.
3. Output ONLY the raw executable test code with no markdown fences or conversational explanations.
"""
        user_prompt = f"Module Path: {file_path}\n\nCode:\n{code}"

        try:
            loc = len(code.splitlines())
            dyn_max_tokens = min(max(loc * 8, 512), 1500)

            resp = await llm.generate_text(
                system_prompt,
                user_prompt,
                model=settings.DEFAULT_FAST_MODEL,
                max_tokens=dyn_max_tokens,
            )
            test_code = resp.content.strip()

            # Clean reasoning / thinking blocks from reasoning models (e.g. Qwen / DeepSeek)
            test_code = re.sub(r"<think>.*?</think>", "", test_code, flags=re.DOTALL).strip()

            # Robust prompt injection protection: extract code blocks precisely
            match = re.search(r"```[a-zA-Z]*\n(.*?)```", test_code, re.DOTALL)
            if match:
                test_code = match.group(1).strip()
            elif test_code.startswith("```"):
                test_code = "\n".join(test_code.splitlines()[1:-1]).strip()

            t_tokens = getattr(resp, "total_tokens", 0)
            t_cost = getattr(resp, "estimated_cost_usd", 0.0)
            if t_tokens == 0:
                p_t = count_tokens(system_prompt + "\n" + user_prompt)
                c_t = count_tokens(test_code)
                t_tokens = p_t + c_t
                provider_name = getattr(llm, "provider", "openai")
                t_cost = calculate_cost(p_t, c_t, provider=provider_name)
            step_tokens += t_tokens
            step_cost += t_cost

        except Exception as e:
            logger.error(f"Test Generator LLM failed for {file_path}: {e}")
            await redis_engine.publish_workflow_event(state["workflow_id"], {
                "agent": "TestGenAgent",
                "thought": f"CRITICAL ERROR: AI Provider unavailable. Halting workflow. {str(e)}",
            })
            raise RuntimeError(f"AI Provider failure in TestGenAgent: {str(e)}") from e

        ext = os.path.splitext(file_path)[1]
        safe_name = file_path.replace('/', '_').replace('\\', '_').replace('.', '_')

        if ext in ['.js', '.jsx', '.ts', '.tsx']:
            test_file_path = f"tests/{safe_name}.test{ext}"
        elif ext == '.java':
            test_file_path = f"src/test/java/{safe_name}Test.java"
        else:
            test_file_path = f"tests/test_{safe_name}{ext if ext else '.py'}"

        git_engine.write_file_content(state["repo_path"], test_file_path, test_code)

        generated_tests.append({
            "test_file": test_file_path,
            "target_file": file_path,
            "code": test_code,
        })

    end_ts = datetime.now(UTC).isoformat()
    await redis_engine.publish_workflow_event(state["workflow_id"], {
        "agent": "TestGenAgent",
        "thought": f"Generated {len(generated_tests)} regression test files.",
        "tests": generated_tests,
        "timestamp": end_ts,
    })

    return {
        "current_step": "TestGenAgent",
        "generated_tests": generated_tests,
        "total_tokens": step_tokens,
        "total_cost_usd": step_cost,
        "thought_stream": [{
            "agent": "TestGenAgent",
            "thought": f"Synthesized {len(generated_tests)} test suites for validation.",
            "timestamp": end_ts,
        }],
    }
