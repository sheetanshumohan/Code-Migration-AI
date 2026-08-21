"""
Main FastAPI Application Entrypoint
Integrates Clean Architecture layers, CORS, Routers, Observability, and Lifespan managers.
"""

import typing
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import get_async_db

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.graph import router as graph_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.reports import router as reports_router
from app.api.v1.repositories import router as repo_router
from app.api.v1.sandbox import router as sandbox_router
from app.api.v1.search import router as search_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.workflows import router as workflow_router
from app.api.websocket import router as ws_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.telemetry import init_telemetry
from app.infrastructure.database.neo4j.driver import neo4j_engine
from app.infrastructure.database.qdrant.client import qdrant_engine
from app.infrastructure.database.redis.client import redis_engine

# Initialize structured logging
setup_logging()
logger = get_logger("codemigration.main")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application Lifespan: Manage database connections and cleanup."""
    logger.info("Initializing Code Migration AI platform services...")

    # 1. PostgreSQL Schema Management is now strictly handled by Alembic CLI.
    # No dynamic create_all() is executed here to prevent production schema drift.

    # 2. Connect Polyglot Persistence Engines
    await neo4j_engine.connect()
    await qdrant_engine.connect()
    await redis_engine.connect()

    logger.info("Code Migration AI platform initialized and ready for traffic.")
    yield

    # Teardown
    logger.info("Shutting down Code Migration AI services...")
    await neo4j_engine.close()
    await qdrant_engine.close()
    await redis_engine.close()
    logger.info("All services shut down cleanly.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Agentic Code Modernization, Migration & Refactoring Platform",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

from starlette.middleware.sessions import SessionMiddleware

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Session for Authlib (Google OAuth)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="codemigration_session",
    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
)

# Initialize Observability (Prometheus, OTel, Sentry)
init_telemetry(app)

# Register REST & WebSocket API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(repo_router, prefix=settings.API_V1_STR)
app.include_router(workflow_router, prefix=settings.API_V1_STR)
app.include_router(graph_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(search_router, prefix=settings.API_V1_STR)
app.include_router(sandbox_router, prefix=settings.API_V1_STR)

app.include_router(uploads_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)
app.include_router(metrics_router, prefix=settings.API_V1_STR)
app.include_router(subscriptions_router, prefix=f"{settings.API_V1_STR}/subscriptions", tags=["subscriptions"])
app.include_router(ws_router, prefix=settings.API_V1_STR)
app.include_router(ws_router)


@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
async def health_check() -> dict:
    """Enterprise health check endpoint verifying all subsystem states actively."""
    # Active Ping Checks
    pg_status = "unhealthy"
    try:
        from app.infrastructure.database.postgres.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            pg_status = "ready"
    except Exception as e:
        logger.error(f"Postgres health check failed: {e}")

    redis_status = "ready" if redis_engine._redis and await redis_engine._redis.ping() else "unhealthy"

    neo4j_status = "unhealthy"
    try:
        if neo4j_engine._driver:
            await neo4j_engine._driver.verify_connectivity()
            neo4j_status = "ready"
    except Exception:
        pass

    qdrant_status = "unhealthy"
    try:
        if qdrant_engine._client:
            await qdrant_engine._client.get_collections()
            qdrant_status = "ready"
    except Exception:
        pass

    all_healthy = all(s == "ready" for s in [pg_status, redis_status, neo4j_status, qdrant_status])

    return {
        "status": "healthy" if all_healthy else "degraded",
        "service": "codemigration-api",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "polyglot_persistence": {
            "postgres": pg_status,
            "neo4j": neo4j_status,
            "qdrant": qdrant_status,
            "redis": redis_status,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Global Exception Handlers — guarantee every error is JSON with a `detail` key
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Normalize all HTTPExceptions to a consistent JSON envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 422 validation errors in a structured JSON format readable by the frontend."""
    errors = exc.errors()
    # Build a human-readable summary for the first error
    first = errors[0] if errors else {}
    field = ".".join(str(loc) for loc in first.get("loc", [])[1:]) or "field"
    summary = f'Validation error on "{field}": {first.get("msg", "Invalid value")}'
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": summary,
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — guarantees uniform JSON error envelope for unhandled exceptions."""
    logger.error("Unhandled server exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc) if settings.DEBUG else "An unexpected server error occurred. Our engineering team has been notified.",
        },
    )
