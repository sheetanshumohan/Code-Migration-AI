"""
Unit Tests for Dynamic Framework Migration Features
Validates that custom user constraints (source framework, target language, custom goals)
are correctly parsed, stored in state, and injected into the LLM system prompts.
"""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.api.v1.workflows import StartMigrationRequest
from app.infrastructure.agents.nodes.planner import planner_node
from app.infrastructure.agents.state import MigrationWorkflowState

pytestmark = pytest.mark.asyncio


def test_start_migration_request_validation():
    """Verify that the StartMigrationRequest accepts the new dynamic routing parameters."""
    req = StartMigrationRequest(
        repository_id="repo-123",
        workflow_type="framework_migration",
        source_framework="Redux Legacy",
        target_framework="Zustand",
        target_language="TypeScript",
        custom_goal="Migrate all createStore to Zustand hooks."
    )
    assert req.source_framework == "Redux Legacy"
    assert req.target_framework == "Zustand"
    assert req.target_language == "TypeScript"
    assert req.custom_goal == "Migrate all createStore to Zustand hooks."


@pytest.fixture
def mock_dynamic_repo_state() -> MigrationWorkflowState:
    return {
        "workflow_id": str(uuid.uuid4()),
        "organization_id": "org_123",
        "repository_id": "repo_123",
        "repo_path": "/tmp/mock_repo",
        "workflow_type": "framework_migration",
        "source_framework": "Redux Legacy",
        "target_framework": "Zustand",
        "target_language": "TypeScript",
        "custom_goal": "Migrate all createStore to Zustand hooks.",
        "file_list": ["store.js", "actions.js"],
        "plan": [],
        "current_task_index": 0,
        "ast_summary": {"nodes": 10},
        "status": "planning",
        "current_step": "initialization",
        "retry_count": 0,
        "max_retries": 3,
        "is_human_approved": False,
        "detected_languages": [],
        "detected_frameworks": [],
        "dependency_graph": {},
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


async def test_planner_node_dynamic_prompt_injection(mock_dynamic_repo_state):
    """
    Tests that the planner node successfully reads the custom dynamic framework parameters
    and injects them into the generated LLM prompt.
    """
    with patch("app.infrastructure.agents.nodes.planner.llm_factory.get_gateway") as mock_get_llm:
        
        # Mock LLM API response to prevent live network calls
        mock_llm_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '''
        ```json
        {
            "plan": [
                {"title": "Setup Zustand", "target_files": ["store.js"]}
            ]
        }
        ```
        '''
        mock_response.total_tokens = 200
        mock_response.estimated_cost_usd = 0.002
        
        # Keep track of what prompt was passed to the LLM
        mock_llm_instance.generate_text.return_value = mock_response
        mock_get_llm.return_value = mock_llm_instance

        # Execute node
        result = await planner_node(mock_dynamic_repo_state)

        # Ensure the LLM was called
        mock_llm_instance.generate_text.assert_called_once()
        
        # Extract the prompt passed to the LLM
        call_args = mock_llm_instance.generate_text.call_args
        prompt_used = call_args[1].get('prompt') or call_args[0][0]
        
        # Verify our custom dynamic inputs made it into the prompt!
        assert "Redux Legacy" in prompt_used
        assert "Zustand" in prompt_used
        assert "TypeScript" in prompt_used
        assert "Migrate all createStore to Zustand hooks." in prompt_used
        
        # Verify the node output is correctly structured
        assert result["current_step"] == "PlannerAgent"
        assert len(result["plan"]) == 1
        assert result["plan"][0]["title"] == "Setup Zustand"
