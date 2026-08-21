"""
Prompt Validator Node for LangGraph
Validates the user's custom objective to ensure it is not too vague.
"""
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.agents.state import MigrationWorkflowState
from app.infrastructure.ai.factory import llm_factory

try:
    from langsmith import traceable
except ImportError:
    traceable = lambda *args, **kwargs: (lambda func: func) if (args and not callable(args[0])) else (args[0] if args else (lambda func: func))

logger = get_logger("codemigration.agent.prompt_validator")

class PromptValidationResult(BaseModel):
    is_valid: bool = Field(description="True if the prompt is specific and actionable, False if it is too vague or lacks sufficient architectural context.")
    reason: str = Field(description="If invalid, a specific reason why and what the user should provide instead.")

@traceable(name="PromptValidatorNode", run_type="chain")
async def prompt_validator_node(state: MigrationWorkflowState) -> dict[str, Any]:
    """Validates the migration goal to prevent garbage-in garbage-out."""
    workflow_type = state.get("workflow_type")

    # We only strongly validate custom goals
    if workflow_type != "custom_modernization":
        return {"current_task": "prompt_validation"}

    custom_goal = state.get("custom_goal", "")
    target_framework = state.get("target_framework", "")
    source_framework = state.get("source_framework", "")

    if not custom_goal or len(custom_goal.strip()) < 10:
        logger.error("Prompt validation failed: Objective is too short.")
        # Halt workflow
        raise ValueError("Custom objective is too short or missing. Please provide a detailed architectural objective.")

    prompt = f"""
    You are an elite, highly rigorous Enterprise Software Architect reviewing a codebase migration request.
    Your sole purpose is to evaluate whether the user's objective provides sufficient architectural depth, 
    actionable constraints, and technical specificity for an autonomous AI coding agent to execute safely 
    and effectively.

    MIGRATION CONTEXT:
    ------------------
    Source Framework: {source_framework or 'None provided'}
    Target Framework: {target_framework or 'None provided'}
    User's Proposed Objective: "{custom_goal}"
    
    EVALUATION CRITERIA:
    --------------------
    An objective is ONLY VALID if it explicitly addresses at least two of the following dimensions:
    1. Architectural Patterns (e.g., MVC, Hexagonal, Microservices, Event-Driven, Repository pattern).
    2. Specific Libraries/Dependencies (e.g., using React Router v6, Prisma ORM, Tailwind CSS).
    3. Structural Constraints (e.g., strict separation of concerns, specific file naming conventions, monorepo structure).
    4. Migration Strategy (e.g., strangler fig pattern, incremental component replacement, API-first).
    5. State Management & Data Flow (e.g., Redux Toolkit, Context API, React Query).
    
    FAILURE MODES (INVALIDATE IF PRESENT):
    --------------------------------------
    - Vague platitudes: "Make it better", "Improve performance", "Refactor the code".
    - High-level buzzwords without implementation details: "Migrate to Next.js", "Make it cloud-native".
    - Lack of "HOW": Describing the end state without any technical directives on how to achieve it.
    
    YOUR OUTPUT:
    ------------
    Assess the objective strictly against these criteria. If it fails, provide a precise, educational 
    reason detailing EXACTLY what technical dimensions are missing, and give a brief example of how 
    the user could improve their prompt.
    """

    gateway = llm_factory.get_gateway()
    try:
        response = await gateway.generate_structured(
            system_prompt="You are a strict architectural prompt validator.",
            user_prompt=prompt,
            response_model=PromptValidationResult,
            model=settings.DEFAULT_FAST_MODEL,
        )

        if not response.is_valid:
            logger.error(f"Prompt validation failed: {response.reason}")
            # Raising ValueError here will halt the pipeline and set the workflow status to error
            raise ValueError(f"Custom Objective is too vague: {response.reason}. Please use the 'Enhance Objective' button to improve it.")

        logger.info("Prompt validation passed.")
        return {"current_task": "prompt_validation"}

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error during prompt validation: {str(e)}")
        # On LLM error, default to letting it pass rather than completely blocking the system
        return {"current_task": "prompt_validation"}
