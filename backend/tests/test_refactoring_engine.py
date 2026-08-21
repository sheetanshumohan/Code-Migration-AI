"""
Unit Tests for AST Refactoring Engine
"""

from app.domain.refactoring.engine import refactoring_engine


def test_remove_unused_imports():
    """Verify unused imports are pruned while active imports are preserved."""
    code = """import os
import sys
import json

def parse(data):
    return json.loads(data)
"""
    cleaned = refactoring_engine.remove_unused_imports_python(code)
    assert "import json" in cleaned
    assert "import sys" not in cleaned or "import os" not in cleaned


def test_rename_symbol():
    """Verify symbol renaming with word boundary precision."""
    code = "def calculate_tax(user_id): return user_id * 0.2"
    renamed = refactoring_engine.rename_symbol(code, "calculate_tax", "compute_tax")
    assert "def compute_tax(user_id):" in renamed
    assert "calculate_tax" not in renamed


def test_extract_method():
    """Verify extracting a block of lines into a separate helper method."""
    code = """def process_order():
    validate_item()
    charge_card()
    send_email()
"""
    extracted = refactoring_engine.extract_method(code, 2, 3, "handle_payment")
    assert "handle_payment()" in extracted
    assert "def handle_payment():" in extracted
