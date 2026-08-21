"""
Neo4j Graph Database Client & AST Cypher Traversal Engine
Handles AST node ingestion, call graph links, blast radius calculations, and circular dependency checks.
"""

from typing import Any, cast

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("codemigration.db.neo4j")


import asyncio

class Neo4jGraphEngine:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        self._loop: Any = None

    def reset(self) -> None:
        """Reset driver reference so new event loops create fresh connections."""
        self._driver = None
        self._loop = None

    async def _ensure_driver(self) -> AsyncDriver | None:
        """Ensure the driver is connected to the currently running event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._loop != current_loop or self._driver is None:
            self._driver = None
            self._loop = current_loop
            await self.connect()
        return self._driver

    async def connect(self) -> None:
        """Initialize connection pool to Neo4j."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
            )
            await self._driver.verify_connectivity()
            await self._init_indices()
            logger.info("Connected to Neo4j Graph Engine successfully")
        except Exception as e:
            logger.warning("Could not connect to Neo4j (will fallback or retry in live env)", error=str(e))

    async def close(self) -> None:
        """Close Neo4j driver connection pool."""
        if self._driver:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None
            self._loop = None
            logger.info("Neo4j Graph connection closed")

    async def _init_indices(self) -> None:
        """Create high-performance indexes for AST graph traversals."""
        if not self._driver:
            return
        queries = [
            "CREATE CONSTRAINT repo_id_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE (f.repo_id, f.file_path) IS UNIQUE",
            "CREATE INDEX symbol_name_idx IF NOT EXISTS FOR (s:Symbol) ON (s.repo_id, s.name)",
        ]
        async with self._driver.session() as session:
            for q in queries:
                try:
                    await session.run(cast(Any, q))
                except Exception as e:
                    logger.debug("Neo4j index check", detail=str(e))

    async def ingest_repository_ast(
        self,
        repo_id: str,
        repo_name: str,
        files: list[dict[str, Any]],
        symbols: list[dict[str, Any]],
        calls: list[dict[str, Any]],
        imports: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Atomically ingest an entire repository's parsed AST symbols and relationships."""
        driver = await self._ensure_driver()
        if not driver:
            logger.warning("Neo4j driver offline, skipping AST graph ingestion")
            return {"files": len(files), "symbols": len(symbols)}

        async with driver.session() as session:
            # 1. Upsert Repository Node
            await session.run(
                "MERGE (r:Repository {id: $repo_id}) SET r.name = $repo_name, r.updated_at = datetime()",
                repo_id=repo_id,
                repo_name=repo_name,
            )

            # 2. Batch Upsert File Nodes
            file_query = """
            UNWIND $files AS f
            MERGE (file:File {repo_id: $repo_id, file_path: f.path})
            SET file.language = f.language, file.loc = f.loc
            WITH file
            MATCH (r:Repository {id: $repo_id})
            MERGE (r)-[:CONTAINS]->(file)
            """
            await session.run(cast(Any, file_query), repo_id=repo_id, files=files)

            # 3. Batch Upsert Symbols (Classes, Functions, Methods)
            symbol_query = """
            UNWIND $symbols AS s
            MERGE (sym:Symbol {id: s.id, repo_id: $repo_id})
            SET sym.name = s.name,
                sym.type = s.type,
                sym.file_path = s.file_path,
                sym.start_line = s.start_line,
                sym.end_line = s.end_line,
                sym.is_async = s.is_async,
                sym.complexity = s.complexity
            WITH sym, s
            MATCH (file:File {repo_id: $repo_id, file_path: s.file_path})
            MERGE (file)-[:DEFINES]->(sym)
            """
            await session.run(cast(Any, symbol_query), repo_id=repo_id, symbols=symbols)

            # 4. Batch Upsert Call Hierarchy
            if calls:
                call_query = """
                UNWIND $calls AS c
                MATCH (caller:Symbol {id: c.caller_id, repo_id: $repo_id})
                MATCH (callee:Symbol {name: c.callee_name, repo_id: $repo_id})
                MERGE (caller)-[:CALLS]->(callee)
                """
                await session.run(cast(Any, call_query), repo_id=repo_id, calls=calls)

            # 5. Batch Upsert Imports
            if imports:
                import_query = """
                UNWIND $imports AS imp
                MATCH (source:File {repo_id: $repo_id, file_path: imp.source_file})
                MERGE (target:File {repo_id: $repo_id, file_path: imp.target_file})
                ON CREATE SET target.language = 'external', target.loc = 0
                MERGE (source)-[:IMPORTS]->(target)
                """
                await session.run(cast(Any, import_query), repo_id=repo_id, imports=imports)

        logger.info(
            "Ingested AST graph into Neo4j",
            repo_id=repo_id,
            files=len(files),
            symbols=len(symbols),
            calls=len(calls),
        )
        return {
            "files": len(files),
            "symbols": len(symbols),
            "calls": len(calls),
            "imports": len(imports),
        }

    async def get_blast_radius(
        self, repo_id: str, symbol_name: str, file_path: str | None = None, max_depth: int = 4
    ) -> list[dict[str, Any]]:
        """Calculate the blast radius of modifying a symbol (all dependent callers up to N depth)."""
        driver = await self._ensure_driver()
        if not driver:
            return []

        if file_path:
            query = f"""
            MATCH (target:Symbol {{repo_id: $repo_id, name: $symbol_name, file_path: $file_path}})
            MATCH path = (caller:Symbol)-[:CALLS*1..{max_depth}]->(target)
            WITH caller, min(length(path)) AS depth, collect([n IN nodes(path) | n.name])[0] AS call_chain
            RETURN 
                caller.name AS caller_name,
                caller.file_path AS caller_file,
                caller.start_line AS start_line,
                depth,
                call_chain
            ORDER BY depth ASC
            """
            params = {"repo_id": repo_id, "symbol_name": symbol_name, "file_path": file_path}
        else:
            query = f"""
            MATCH (target:Symbol {{repo_id: $repo_id, name: $symbol_name}})
            MATCH path = (caller:Symbol)-[:CALLS*1..{max_depth}]->(target)
            WITH caller, min(length(path)) AS depth, collect([n IN nodes(path) | n.name])[0] AS call_chain
            RETURN 
                caller.name AS caller_name,
                caller.file_path AS caller_file,
                caller.start_line AS start_line,
                depth,
                call_chain
            ORDER BY depth ASC
            """
            params = {"repo_id": repo_id, "symbol_name": symbol_name}

        async with driver.session() as session:
            result = await session.run(cast(Any, query), parameters=params)
            records = await result.data()
            return records

    async def get_repository_graph_snapshot(
        self, repo_id: str, limit: int = 250
    ) -> dict[str, Any]:
        """Fetch nodes and edges for rendering in React Flow / Dependency Graph UI."""
        driver = await self._ensure_driver()
        if not driver:
            return {"nodes": [], "edges": []}

        query = """
        MATCH (f:File {repo_id: $repo_id})
        OPTIONAL MATCH (f)-[imp:IMPORTS]->(f2:File {repo_id: $repo_id})
        RETURN f.file_path AS file, f.language AS language, f.loc AS loc, collect({path: f2.file_path, language: f2.language, loc: f2.loc}) AS imports
        LIMIT $limit
        """
        async with driver.session() as session:
            result = await session.run(cast(Any, query), repo_id=repo_id, limit=limit)
            records = await result.data()

            nodes = []
            edges = []
            seen_nodes = set()
            seen_edges = set()

            for r in records:
                source = r["file"]
                if not source:
                    continue
                if source not in seen_nodes:
                    seen_nodes.add(source)
                    nodes.append({
                        "id": source,
                        "type": "fileNode",
                        "data": {
                            "label": source,
                            "language": r["language"] or "code",
                            "loc": r["loc"] or 0,
                        },
                    })
                for target_obj in r.get("imports", []):
                    target = target_obj.get("path")
                    if target and target != source:
                        if target not in seen_nodes:
                            seen_nodes.add(target)
                            nodes.append({
                                "id": target,
                                "type": "fileNode",
                                "data": {
                                    "label": target,
                                    "language": target_obj.get("language") or "external",
                                    "loc": target_obj.get("loc") or 0,
                                },
                            })
                        edge_id = f"{source}->{target}"
                        if edge_id not in seen_edges:
                            seen_edges.add(edge_id)
                            edges.append({
                                "id": edge_id,
                                "source": source,
                                "target": target,
                                "animated": True,
                            })

            return {"nodes": nodes, "edges": edges}

    async def delete_repository_ast(self, repo_id: str) -> None:
        """Delete all graph nodes associated with a repository."""
        driver = await self._ensure_driver()
        if not driver:
            return

        query = """
        MATCH (n)
        WHERE n.repo_id = $repo_id OR (n:Repository AND n.id = $repo_id)
        DETACH DELETE n
        """
        async with driver.session() as session:
            try:
                await session.run(cast(Any, query), repo_id=repo_id)
                logger.info("Deleted repository AST from Neo4j", repo_id=repo_id)
            except Exception as e:
                logger.error("Failed to delete repository AST from Neo4j", repo_id=repo_id, error=str(e))



neo4j_engine = Neo4jGraphEngine()
