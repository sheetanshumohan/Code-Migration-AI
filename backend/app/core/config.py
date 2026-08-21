"""
Core Configuration Module for Code Migration AI
Pydantic v2 Settings with strict environment variable loading.
"""

from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # General
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Code Migration AI"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "super-secret-key-change-in-production-min-32-chars-hex-entropy"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = "http://localhost:5173"

    # Email / SMTP (required for real password reset emails)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@codemigration.ai"
    SMTP_USE_TLS: bool = True

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Prevent production deployment with default insecure values."""
        if self.ENVIRONMENT == "production":
            default_key = "super-secret-key-change-in-production-min-32-chars-hex-entropy"
            if self.SECRET_KEY == default_key:
                raise ValueError(
                    "FATAL: SECRET_KEY must be changed from the default value before deploying to production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError("FATAL: SECRET_KEY must be at least 32 characters in production.")
        return self

    # Google OAuth
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # Stripe Settings
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # Allows a comma-separated string or list to be parsed into a list of origins
    BACKEND_CORS_ORIGINS: list[str] | str = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(i) for i in parsed]
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i) for i in v]
        return []

    # Primary Database (PostgreSQL)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_secure_pass"
    POSTGRES_DB: str = "codemigration_db"
    POSTGRES_ASYNC_URI: str | None = None

    @field_validator("POSTGRES_ASYNC_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info) -> str:
        if isinstance(v, str) and v:
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            return v
        data = info.data
        user = data.get("POSTGRES_USER", "postgres")
        pwd = data.get("POSTGRES_PASSWORD", "postgres_secure_pass")
        server = data.get("POSTGRES_SERVER", "localhost")
        port = data.get("POSTGRES_PORT", 5432)
        db = data.get("POSTGRES_DB", "codemigration_db")
        return f"postgresql+asyncpg://{user}:{pwd}@{server}:{port}/{db}"

    # Graph Database (Neo4j)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j_secure_pass"

    # Vector Database (Qdrant)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None
    QDRANT_TIMEOUT_SECONDS: int = 10
    QDRANT_COLLECTION_SYMBOLS: str = "codemigration_symbols"
    QDRANT_COLLECTION_DOCS: str = "codemigration_docs"

    # Distributed Task Queue & Cache (Redis)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_TIME_LIMIT_SECONDS: int = 1800
    WORKFLOW_MAX_RETRIES: int = 3

    # AI & LLM Providers
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    PERPLEXITY_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DEFAULT_LLM_PROVIDER: str = "openai" # "openai", "anthropic", "gemini", "ollama", "groq", "perplexity"
    DEFAULT_FRONTIER_MODEL: str = "gpt-4o"
    DEFAULT_FAST_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-5-sonnet-20240620"
    GEMINI_DEFAULT_MODEL: str = "gemini-2.5-flash"
    GROQ_DEFAULT_MODEL: str = "qwen/qwen3.6-27b"

    # Version Control
    GITHUB_TOKEN: str | None = None

    # Observability
    ENABLE_TELEMETRY: bool = True
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = "http://localhost:4317"
    SENTRY_DSN: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Sandboxes
    WORKSPACE_DIR: str = "./data/workspace_sandboxes"
    MAX_REPO_CLONE_SIZE_MB: int = 500
    SANDBOX_EXECUTION_TIMEOUT_SECONDS: int = 120
    SANDBOX_DOCKER_IMAGE: str = "python:3.13-slim"

    # Stripe Pricing (in cents)
    STRIPE_PRO_PRICE_CENTS: int = 500        # $5.00/month
    STRIPE_UNLIMITED_PRICE_CENTS: int = 20000 # $200.00/month

    # Workflow
    WORKFLOW_TOTAL_STEPS: int = 6
    WORKFLOW_RECURSION_LIMIT: int = 250


settings = Settings()
