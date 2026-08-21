"""
LangGraph Multi-Agent State Definition
Type-safe state container tracking the complete context of an autonomous migration/refactoring workflow.
"""

import operator
from typing import Annotated, Any, TypedDict


class FileChange(TypedDict):
    file_path: str
    original_code: str
    transformed_code: str
    diff: str
    status: str # "pending", "applied", "failed"
    explanation: str


class TaskItem(TypedDict):
    id: str
    title: str
    description: str
    target_files: list[str]
    dependencies: list[str]
    status: str # "pending", "in_progress", "completed", "failed"


class ValidationResult(TypedDict):
    passed: bool
    linter_errors: list[str]
    type_check_errors: list[str]
    test_failures: list[str]
    security_vulnerabilities: list[str]
    raw_logs: str


class MigrationWorkflowState(TypedDict):
    # Workflow Metadata
    workflow_id: str
    organization_id: str
    repository_id: str
    repo_path: str
    workflow_type: str # "framework_migration", "solid_refactor", "security_remediation", "state_management_migration", "custom_modernization"
    source_framework: str | None
    target_language: str | None
    target_framework: str | None
    custom_goal: str | None

    # Progress & Routing
    status: str # "planning", "awaiting_approval", "executing", "validating", "completed", "failed"
    current_step: str
    retry_count: int
    max_retries: int
    is_human_approved: bool

    # Repository Intelligence Context
    file_list: list[str]
    detected_languages: list[str]
    detected_frameworks: list[str]
    ast_summary: dict[str, Any]
    dependency_graph: dict[str, Any]

    # Migration Plan DAG
    plan: list[TaskItem]
    current_task_index: int

    # Transformed Files & Code Diffs
    file_changes: Annotated[list[FileChange], operator.add]
    generated_tests: Annotated[list[dict[str, str]], operator.add]

    # Quality Assurance & Sandboxing
    validation_results: ValidationResult | None
    reflection_feedback: str | None

    # Documentation & Pull Request
    migration_report: str | None
    pr_title: str | None
    pr_description: str | None
    pr_url: str | None

    # Real-Time Telemetry & Thoughts Stream
    thought_stream: Annotated[list[dict[str, Any]], operator.add]
    total_tokens: Annotated[int, operator.add]
    total_cost_usd: Annotated[float, operator.add]
