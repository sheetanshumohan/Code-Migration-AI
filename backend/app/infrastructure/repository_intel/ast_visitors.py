"""
AST Code Visitors & Semantic Chunking Engine
Deconstructs source code files into semantic AST chunks (functions, classes, methods) for vector embeddings and blast radius queries.
"""

from typing import Any

from app.core.logging import get_logger
from app.infrastructure.repository_intel.ast_parser import ast_parser

logger = get_logger("codemigration.intel.visitors")


class CodeChunk:
    def __init__(
        self,
        chunk_id: str,
        file_path: str,
        symbol_name: str,
        symbol_type: str, # "class", "function", "module"
        language: str,
        code_content: str,
        start_line: int,
        end_line: int,
        complexity: int = 1,
    ) -> None:
        self.chunk_id = chunk_id
        self.file_path = file_path
        self.symbol_name = symbol_name
        self.symbol_type = symbol_type
        self.language = language
        self.code_content = code_content
        self.start_line = start_line
        self.end_line = end_line
        self.complexity = complexity

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "symbol_name": self.symbol_name,
            "symbol_type": self.symbol_type,
            "language": self.language,
            "code_content": self.code_content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "complexity": self.complexity,
        }


class ASTSemanticChunker:
    """Chunks source code into meaningful semantic blocks preserving AST boundaries."""

    @staticmethod
    def chunk_file(file_path: str, content: str) -> list[CodeChunk]:
        parsed = ast_parser.parse_file(file_path, content)
        chunks: list[CodeChunk] = []
        lines = content.splitlines()

        # 1. Chunk identified classes
        for cls in parsed.get("classes", []):
            start = max(1, cls.get("start_line", 1))
            end = min(len(lines), cls.get("end_line", len(lines)))
            cls_code = "\n".join(lines[start - 1 : end])
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}::{cls['name']}",
                    file_path=file_path,
                    symbol_name=cls["name"],
                    symbol_type="class",
                    language=parsed["language"],
                    code_content=cls_code,
                    start_line=start,
                    end_line=end,
                    complexity=cls.get("complexity", 1),
                )
            )

        # 2. Chunk identified standalone functions
        for fn in parsed.get("functions", []):
            start = max(1, fn.get("start_line", 1))
            end = min(len(lines), fn.get("end_line", len(lines)))
            fn_code = "\n".join(lines[start - 1 : end])
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}::{fn['name']}",
                    file_path=file_path,
                    symbol_name=fn["name"],
                    symbol_type="function",
                    language=parsed["language"],
                    code_content=fn_code,
                    start_line=start,
                    end_line=end,
                    complexity=fn.get("complexity", 1),
                )
            )

        # 3. Fallback: If file has no distinct functions/classes (e.g. scripts or configs), treat whole file as a chunk
        if not chunks and content.strip():
            chunks.append(
                CodeChunk(
                    chunk_id=f"{file_path}::module",
                    file_path=file_path,
                    symbol_name="module",
                    symbol_type="module",
                    language=parsed["language"],
                    code_content=content,
                    start_line=1,
                    end_line=len(lines),
                    complexity=1,
                )
            )

        return chunks


ast_chunker = ASTSemanticChunker()
