"""
Repository Analyst Agent Node for LangGraph
Performs full-repo AST parsing, language/framework detection, and graph persistence.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.infrastructure.agents.state import MigrationWorkflowState
from app.infrastructure.database.neo4j.driver import neo4j_engine
from app.infrastructure.database.redis.client import redis_engine
from app.infrastructure.repository_intel.ast_parser import ast_parser
from app.infrastructure.repository_intel.git_engine import git_engine

try:
    from langsmith import traceable
except ImportError:
    traceable = lambda *args, **kwargs: (lambda func: func) if (args and not callable(args[0])) else (args[0] if args else (lambda func: func))

logger = get_logger("codemigration.agent.analyst")


@traceable(name="RepoAnalystNode", run_type="chain")
async def repo_analyst_node(state: MigrationWorkflowState) -> dict[str, Any]:
    """LangGraph node: Ingests repository files, computes AST, and populates Neo4j."""
    is_cancelled = await redis_engine.get_json(f"workflow_cancelled:{state['workflow_id']}")
    if is_cancelled:
        logger.info("Workflow execution cancelled by user. Halting RepoAnalystAgent.", workflow_id=state["workflow_id"])
        raise asyncio.CancelledError("Workflow was cancelled by operator.")

    logger.info("Executing Repository Analyst Agent", repo_id=state["repository_id"])

    await redis_engine.publish_workflow_event(state["workflow_id"], {
        "agent": "RepoAnalystAgent",
        "thought": "Scanning workspace directory and constructing AST symbol tree...",
        "timestamp": datetime.now(UTC).isoformat(),
    })

    repo_path = state["repo_path"]
    file_list = git_engine.list_repository_files(repo_path)

    detected_languages = set()
    all_symbols = []
    all_imports = []
    all_calls = []
    file_metadata = []

    for rel_file in file_list:
        try:
            content = git_engine.read_file_content(repo_path, rel_file)
            parsed = ast_parser.parse_file(rel_file, content)
            if parsed["language"] != "unknown":
                detected_languages.add(parsed["language"])
            file_metadata.append({"path": rel_file, "language": parsed["language"], "loc": parsed["loc"]})
            all_symbols.extend(parsed["symbols"])
            all_imports.extend(parsed["imports"])

            if parsed.get("calls"):
                all_calls.extend(parsed["calls"])
        except Exception as e:
            logger.warning("Failed to parse AST for file", file=rel_file, error=str(e))

    # Resolve relative imports to absolute target file paths
    import os
    all_file_set = set(file_list)
    resolved_imports = []
    for imp in all_imports:
        source_f = imp.get("source_file", "")
        target_raw = imp.get("target_symbol", "")
        target_clean = target_raw.strip("\"'`;")

        if target_clean.startswith('.'):
            # Resolve relative import
            source_dir = os.path.dirname(source_f)
            cand = os.path.normpath(os.path.join(source_dir, target_clean)).replace('\\', '/')
            matched = False
            for ext in ['', '.js', '.jsx', '.ts', '.tsx', '.py', '/index.js', '/index.ts', '/index.tsx']:
                test_path = cand + ext
                if test_path in all_file_set:
                    imp["target_file"] = test_path
                    resolved_imports.append(imp)
                    matched = True
                    break
            if not matched:
                imp["target_file"] = cand
                resolved_imports.append(imp)
        elif not target_clean.startswith('.'):
            # External or third-party package (e.g. 'react', 'express', 'axios')
            imp["target_file"] = target_clean
            resolved_imports.append(imp)

    # Persist AST into Neo4j
    await neo4j_engine.ingest_repository_ast(
        repo_id=state["repository_id"],
        repo_name=state["repository_id"],
        files=file_metadata,
        symbols=all_symbols,
        calls=all_calls,
        imports=resolved_imports,
    )

    summary = {
        "total_files": len(file_list),
        "total_symbols": len(all_symbols),
        "total_calls": len(all_calls),
        "total_imports": len(all_imports),
        "languages": list(detected_languages),
    }

    completion_ts = datetime.now(UTC).isoformat()
    await redis_engine.publish_workflow_event(state["workflow_id"], {
        "agent": "RepoAnalystAgent",
        "thought": f"AST Analysis complete. Extracted {len(all_symbols)} symbols across {len(file_list)} files.",
        "summary": summary,
        "timestamp": completion_ts,
    })

    return {
        "current_step": "RepoAnalystAgent",
        "file_list": file_list,
        "detected_languages": list(detected_languages),
        "ast_summary": summary,
        "thought_stream": [{
            "agent": "RepoAnalystAgent",
            "thought": f"Completed AST and dependency graph extraction for {len(file_list)} files.",
            "timestamp": completion_ts,
        }],
    }
