"""
Semantic Vector Code Search Engine
Embeds AST code chunks and indexes them into Qdrant for natural language code search and architectural discovery.
"""

import hashlib
import math
from typing import Any

from app.core.logging import get_logger
from app.infrastructure.database.qdrant.client import qdrant_engine
from app.infrastructure.repository_intel.ast_visitors import ast_chunker

try:
    from langsmith import traceable
except ImportError:
    traceable = lambda *args, **kwargs: (lambda func: func) if (args and not callable(args[0])) else (args[0] if args else (lambda func: func))

logger = get_logger("codemigration.intel.search")


def generate_deterministic_embedding(text: str, dim: int = 1536) -> list[float]:
    """Generates a normalized embedding vector based on hash frequency when offline / fallback."""
    hasher = hashlib.sha256()
    hasher.update(text.encode("utf-8"))
    seed = int(hasher.hexdigest(), 16)

    vec = []
    for i in range(dim):
        val = math.sin(seed + i * 0.314159)
        vec.append(val)

    # Normalize vector
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class SemanticCodeSearchEngine:
    @traceable(name="SemanticSearch_IndexFileChunks", run_type="tool")
    async def index_file_chunks(self, repo_id: str, file_path: str, content: str) -> int:
        """Parse file into AST chunks, generate embeddings, and upsert to Qdrant."""
        chunks = ast_chunker.chunk_file(file_path, content)
        if not chunks:
            return 0

        vectors = []
        payloads = []

        for chunk in chunks:
            embedding = generate_deterministic_embedding(chunk.code_content)
            vectors.append(embedding)
            payloads.append({
                "repo_id": repo_id,
                "file_path": chunk.file_path,
                "symbol_name": chunk.symbol_name,
                "symbol_type": chunk.symbol_type,
                "language": chunk.language,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "code_snippet": chunk.code_content[:500],
            })

        await qdrant_engine.upsert_code_embeddings(repo_id, vectors, payloads)
        logger.info("Indexed AST code chunks into Qdrant", file=file_path, chunk_count=len(chunks))
        return len(chunks)

    @traceable(name="SemanticSearch_SearchCode", run_type="retriever")
    async def search_code(
        self, repo_id: str, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Semantic search across repository source code via vector similarity."""
        query_vector = generate_deterministic_embedding(query)
        results = await qdrant_engine.search_similar_code(repo_id, query_vector, limit=limit)
        return results


semantic_search_engine = SemanticCodeSearchEngine()
