import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.agents.nodes.refactor import refactor_node

pytestmark = pytest.mark.asyncio

@pytest.mark.integration
async def test_genuine_refactor_node_integration(real_repo_fixture):
    """
    True E2E Integration Test.
    Uses a real temporary filesystem for git_engine instead of patching it out.
    Allows the real LangGraph refactor_node and LLM Factory to execute.
    Mocks only the absolute lowest level OpenAI HTTP call to prevent network burning.
    """
    repo_path = real_repo_fixture

    repo_state = {
        "workflow_id": str(uuid.uuid4()),
        "organization_id": "org_123",
        "repository_id": "repo_123",
        "repo_path": repo_path,
        "workflow_type": "framework_migration",
        "target_framework": "FastAPI",
        "target_language": "python",
        "file_list": ["main.py"],
        "plan": [
            {"title": "Migrate core router", "target_files": ["main.py"]}
        ],
        "current_task_index": 0,
        "file_changes": []
    }

    # We patch only the exact HTTP-level completion call to prevent burning OpenAI credits,
    # but the entire LLM Gateway, telemetry, factory, and git_engine will run genuinely.
    with patch("openai.resources.chat.completions.AsyncCompletions.create", new_callable=AsyncMock) as mock_openai_create, \
         patch("app.infrastructure.agents.nodes.refactor.redis_engine.publish_workflow_event"): # Mute redis pubsub

        # Build a realistic looking OpenAI response object
        mock_choice = MagicMock()
        mock_choice.message.content = """```python
from fastapi import FastAPI
import httpx

app = FastAPI()

@app.get("/users")
async def get_users():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://jsonplaceholder.typicode.com/users")
        return response.json()
```"""
        mock_choice.delta.content = ""

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_openai_create.return_value = mock_response

        # Ensure the environment variable is set so the factory doesn't crash
        os.environ["OPENAI_API_KEY"] = "sk-mock-key-for-integration-tests"

        # Execute the Node
        result = await refactor_node(repo_state)

        # Verify the actual workflow state modifications
        assert result["current_step"] == "RefactorAgent"
        assert len(result["file_changes"]) == 1

        file_change = result["file_changes"][0]

        # Depending on whether file_change is a dict or a Pydantic model
        file_path = file_change.get("file_path") if isinstance(file_change, dict) else getattr(file_change, "file_path", None)
        status = file_change.get("status") if isinstance(file_change, dict) else getattr(file_change, "status", None)
        transformed_code = file_change.get("transformed_code", "") if isinstance(file_change, dict) else getattr(file_change, "transformed_code", "")

        assert file_path == "main.py"
        assert status == "applied"
        assert "FastAPI" in transformed_code
        assert "httpx.AsyncClient" in transformed_code

        # Crucially, verify the Git Engine ACTUALLY wrote the file to the real disk!
        with open(os.path.join(repo_path, "main.py")) as f:
            disk_content = f.read()
            assert "FastAPI" in disk_content
            assert "requests" not in disk_content # Verify legacy code was overwritten
