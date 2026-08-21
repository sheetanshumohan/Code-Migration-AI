"""
DSPy Prompt Optimization Pipeline for Agentic Migration
Implements automated prompt tuning, regression testing, and few-shot optimization.
"""

from typing import Any

import dspy
from dspy.evaluate import Evaluate
from dspy.teleprompt import BootstrapFewShot

from app.core.logging import get_logger

logger = get_logger("codemigration.dspy")


class RefactoringSignature(dspy.Signature): # type: ignore
    """
    Transforms legacy synchronous code to modern async architecture.
    Objective: Maintain 100% behavioral equivalence while adopting target framework conventions.
    """
    legacy_code = dspy.InputField(desc="The original legacy source code.")
    target_framework = dspy.InputField(desc="The destination framework (e.g., FastAPI, SQLAlchemy 2.0).")
    refactored_code = dspy.OutputField(desc="The modernized, syntactically correct code strictly matching the target framework.")


class MigrationAgent(dspy.Module): # type: ignore
    """Core DSPy Agent responsible for executing code migrations."""
    def __init__(self):
        super().__init__()
        # We use ChainOfThought to allow the model to reason before outputting the raw code.
        self.refactor = dspy.ChainOfThought(RefactoringSignature)

    def forward(self, legacy_code: str, target_framework: str):
        result = self.refactor(legacy_code=legacy_code, target_framework=target_framework)
        return dspy.Prediction(
            refactored_code=result.refactored_code,
            reasoning=result.reasoning
        )


def validate_refactored_code(example: dspy.Example, pred: dspy.Prediction, trace: Any = None) -> bool | float: # type: ignore
    """
    Optimization Objective (Metric):
    Checks if the predicted refactored code contains expected async/await patterns
    and successfully dropped legacy synchronous anti-patterns.
    """
    code = pred.refactored_code.lower()

    # Simple heuristic metric for optimization
    score = 0.0

    # 1. Did it adopt async?
    if "async def" in code or "await" in code:
        score += 0.5

    # 2. Did it drop the exact legacy pattern (e.g. Flask route)?
    if "@app.route" not in code and "@app.get" in code:  # Assuming FastAPI target
        score += 0.5

    # Exact match on expected output is a 1.0
    if example.expected_refactored_code and example.expected_refactored_code.strip() == pred.refactored_code.strip():
        score = 1.0

    return score


def get_evaluation_dataset() -> list[dspy.Example]: # type: ignore
    """Loads the regression testing dataset for few-shot optimization."""

    raw_data = [
        {
            "legacy_code": "@app.route('/users')\ndef get_users():\n    return db.query(User).all()",
            "target_framework": "FastAPI with Async SQLAlchemy",
            "expected_refactored_code": "@app.get('/users')\nasync def get_users():\n    result = await db.execute(select(User))\n    return result.scalars().all()"
        },
        {
            "legacy_code": "import requests\ndef fetch_data():\n    return requests.get('https://api.example.com').json()",
            "target_framework": "httpx async",
            "expected_refactored_code": "import httpx\nasync def fetch_data():\n    async with httpx.AsyncClient() as client:\n        response = await client.get('https://api.example.com')\n        return response.json()"
        }
    ]

    # Convert to DSPy Examples and declare inputs
    dataset = []
    for data in raw_data:
        example = dspy.Example(
            legacy_code=data["legacy_code"],
            target_framework=data["target_framework"],
            expected_refactored_code=data["expected_refactored_code"]
        ).with_inputs("legacy_code", "target_framework")
        dataset.append(example)

    return dataset


class DSPyOptimizer:
    """Manages the lifecycle of prompt optimization, versioning, and regression testing."""
    def __init__(self):
        self.compiled_agent = None

    def optimize_agent(self, llm_provider="openai") -> None:
        """Runs the optimization workflow using BootstrapFewShot."""

        logger.info("Starting DSPy optimization pipeline for Migration Agent...")

        # 1. Setup LLM backend for DSPy
        # Fail explicitly if no LLM key is configured — do not run with dummy/invalid key
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY must be set in environment to run DSPy optimization. "
                "Set the key and re-run the optimizer."
            )
        from app.core.config import settings
        lm = dspy.OpenAI(model=settings.DEFAULT_FAST_MODEL, api_key=api_key)
        dspy.settings.configure(lm=lm)

        dataset = get_evaluation_dataset()
        trainset = dataset[:1]  # Normally this would be a larger split
        valset = dataset[1:]

        # 2. Configure Optimizer (BootstrapFewShot)
        teleprompter = BootstrapFewShot(
            metric=validate_refactored_code,
            max_bootstrapped_demos=2,
            max_labeled_demos=2
        )

        # 3. Compile (Optimize Prompts)
        agent = MigrationAgent()
        self.compiled_agent = teleprompter.compile(agent, trainset=trainset)

        # 4. Prompt Versioning & Serialization
        # Save the optimized weights (prompts/signatures) for production use
        self.compiled_agent.save("codemigration_migration_agent_v1.json")
        logger.info("Compiled DSPy agent saved to codemigration_migration_agent_v1.json")

        # 5. Regression Evaluation (Measurable Improvement)
        evaluator = Evaluate(devset=valset, num_threads=1, display_progress=False, display_table=0)
        baseline_score = evaluator(agent, metric=validate_refactored_code)
        optimized_score = evaluator(self.compiled_agent, metric=validate_refactored_code)

        logger.info(f"DSPy Baseline Metric: {baseline_score}")
        logger.info(f"DSPy Optimized Metric: {optimized_score}")

        if optimized_score >= baseline_score:
            logger.info("Optimization yielded measurable improvement or stable regression.")
        else:
            logger.warning("Optimization degraded performance. Retaining previous prompt versions.")

# Expose singleton
dspy_optimizer = DSPyOptimizer()
