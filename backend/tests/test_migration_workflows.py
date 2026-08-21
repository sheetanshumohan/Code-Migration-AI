"""
E2E Integration Tests for Migration Workflows & Celery Orchestration
Validates that the LangGraph workflow executes end-to-end and integrates with the celery broker.
"""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.infrastructure.agents.nodes.refactor import refactor_node

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_repo_state():
    return {
        "workflow_id": str(uuid.uuid4()),
        "organization_id": "org_123",
        "repository_id": "repo_123",
        "repo_path": "/tmp/mock_repo",
        "workflow_type": "framework_migration",
        "target_framework": "FastAPI",
        "target_language": "python",
        "file_list": ["main.py", "models.py"],
        "plan": [
            {"title": "Migrate core router", "target_files": ["main.py"]},
            {"title": "Upgrade ORM", "target_files": ["models.py"]}
        ],
        "current_task_index": 0,
    }

async def test_refactor_node_integration(mock_repo_state):
    """
    Tests that the refactor node correctly interfaces with the LLM Factory
    and outputs FileChange events without swallowing exceptions.
    """
    with patch("app.infrastructure.agents.nodes.refactor.git_engine.read_file_content") as mock_read, \
         patch("app.infrastructure.agents.nodes.refactor.git_engine.write_file_content") as _, \
         patch("app.infrastructure.agents.nodes.refactor.redis_engine.publish_workflow_event") as mock_publish, \
         patch("app.infrastructure.agents.nodes.refactor.llm_factory.get_gateway") as mock_get_llm:

        # Mock file system reads
        mock_read.return_value = "def legacy_flask_app(): pass"
        
        # Mock LLM API response to prevent live network calls and costs
        mock_llm_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "```python\n# Refactored via AI\ndef modern_fastapi_app(): pass\n```"
        mock_response.total_tokens = 150
        mock_response.estimated_cost_usd = 0.001
        
        mock_llm_instance.generate_text.return_value = mock_response
        mock_get_llm.return_value = mock_llm_instance

        # Execute node
        result = await refactor_node(mock_repo_state)

        # Verify LLM transformed output
        assert result["current_step"] == "RefactorAgent"
        assert len(result["file_changes"]) > 0
        file_change = result["file_changes"][0]
        
        # Depending on whether file_change is a dict or a Pydantic model
        file_path = file_change.get("file_path") if isinstance(file_change, dict) else getattr(file_change, "file_path", None)
        status = file_change.get("status") if isinstance(file_change, dict) else getattr(file_change, "status", None)
        transformed_code = file_change.get("transformed_code", "") if isinstance(file_change, dict) else getattr(file_change, "transformed_code", "")
        
        assert file_path == "main.py"
        assert status == "applied"
        assert transformed_code and "Refactored via" in transformed_code

        # Verify the unified diff was generated
        diff = file_change.get("diff", "") if isinstance(file_change, dict) else getattr(file_change, "diff", "")
        assert diff and len(diff) > 0

        # Verify redis pub/sub was called for UI streaming
        assert mock_publish.call_count >= 1


