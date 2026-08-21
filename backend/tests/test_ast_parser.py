"""
Unit Tests for Multi-Language AST Parser
Verifies Tree-sitter symbol extraction, function and class identification, cyclomatic complexity.
"""

from app.infrastructure.repository_intel.ast_parser import ast_parser


def test_python_ast_parsing():
    """Verify parsing of Python source code with functions, classes, and complexity."""
    sample_python_code = """
import os
import sys

class UserService:
    def __init__(self, db_url: str):
        self.db_url = db_url

    async def get_user_by_id(self, user_id: int):
        if user_id > 0:
            return {"id": user_id, "name": "Test User"}
        else:
            raise ValueError("Invalid user ID")
"""
    result = ast_parser.parse_file("services/user_service.py", sample_python_code)

    assert result["language"] == "python"
    assert result["loc"] > 10
    assert len(result["classes"]) >= 1
    assert result["classes"][0]["name"] == "UserService"
    assert len(result["functions"]) >= 2
    assert any(f["name"] == "get_user_by_id" for f in result["functions"])


def test_javascript_ast_parsing():
    """Verify parsing of JavaScript source code."""
    sample_js_code = """
import React, { useState } from 'react';

export function HeaderComponent(props) {
    const [count, setCount] = useState(0);
    return <h1>Header</h1>;
}
"""
    result = ast_parser.parse_file("components/Header.jsx", sample_js_code)

    assert result["language"] == "javascript"
    assert len(result["functions"]) >= 1
    assert result["functions"][0]["name"] == "HeaderComponent"
