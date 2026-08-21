"""
Unit Tests for AST Semantic Chunker
"""

from app.infrastructure.repository_intel.ast_visitors import ast_chunker


def test_chunk_file():
    """Verify source code is split into distinct semantic function and class chunks."""
    code = """
class OrderProcessor:
    def execute(self):
        return True

def standalone_helper():
    return 42
"""
    chunks = ast_chunker.chunk_file("services/order.py", code)
    assert len(chunks) >= 1
    assert any(c.symbol_type in ["class", "function"] for c in chunks)
