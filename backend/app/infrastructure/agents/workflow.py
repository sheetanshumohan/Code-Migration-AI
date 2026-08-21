"""
LangGraph Multi-Agent Workflow State Machine
Assembles the complete Directed Acyclic Graph with cyclical reflection loops and human-in-the-loop gates.
"""

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.core.logging import get_logger

# Extended 14 Agent Nodes
# Base Nodes
from app.infrastructure.agents.nodes.planner import planner_node
from app.infrastructure.agents.nodes.refactor import refactor_node
from app.infrastructure.agents.nodes.repo_analyst import repo_analyst_node
from app.infrastructure.agents.nodes.reviewer import reviewer_node
from app.infrastructure.agents.nodes.test_generator import test_generator_node
from app.infrastructure.agents.nodes.validator import validator_node
from app.infrastructure.agents.nodes.prompt_validator import prompt_validator_node
from app.infrastructure.agents.state import MigrationWorkflowState

logger = get_logger("codemigration.agent.workflow")


def check_validation_results(state: MigrationWorkflowState) -> Literal["check_next_task", "refactor_reflection"]:
    """Conditional router: verify if tests/linters passed, loop for self-healing, or fail."""
    val = state.get("validation_results")
    if val and val.get("passed", False):
        return "check_next_task"

    retries = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if retries < max_retries:
        logger.info("Validation failed, triggering self-healing reflection loop", retry=retries + 1)
        return "refactor_reflection"

    logger.error("Maximum reflection retries exceeded, routing to next task")
    return "check_next_task"


def check_next_task(state: MigrationWorkflowState) -> Literal["refactor", "reviewer"]:
    """Check if there are more tasks in the plan to execute."""
    current_idx = state.get("current_task_index", 0)
    plan = state.get("plan", [])
    if current_idx < len(plan):
        return "refactor"
    return "reviewer"


def build_migration_graph() -> Any:
    workflow = StateGraph(MigrationWorkflowState)  # type: ignore

    # 1. Register Functional Agent Nodes
    workflow.add_node("repo_analyst", repo_analyst_node)
    workflow.add_node("prompt_validator", prompt_validator_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("refactor", refactor_node)
    workflow.add_node("test_generator", test_generator_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("reviewer", reviewer_node)

    # 2. Add Graph Edges & Flow
    workflow.set_entry_point("repo_analyst")
    workflow.add_edge("repo_analyst", "prompt_validator")
    workflow.add_edge("prompt_validator", "planner")
    workflow.add_edge("planner", "refactor")
    workflow.add_edge("refactor", "test_generator")
    workflow.add_edge("test_generator", "validator")

    # Conditional Validation & Self-Healing Loop

    # Loop back for subsequent tasks
    async def increment_task_node(state: MigrationWorkflowState) -> dict[str, Any]:
        """Increments task index to process the next step in the plan DAG."""
        current_idx = state.get("current_task_index", 0)
        return {"current_task_index": current_idx + 1}

    workflow.add_node("increment_task", increment_task_node)

    workflow.add_conditional_edges(
        "validator",
        check_validation_results,
        {
            "check_next_task": "increment_task",
            "refactor_reflection": "refactor",
        },
    )

    workflow.add_conditional_edges(
        "increment_task",
        check_next_task,
        {
            "refactor": "refactor",
            "reviewer": "reviewer",
        }
    )
    workflow.add_edge("reviewer", END)

    # Return uncompiled workflow so it can be compiled with a distributed checkpointer
    return workflow

migration_workflow = build_migration_graph()
