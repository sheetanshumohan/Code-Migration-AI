"""
Telemetry & Observability Module for Code Migration AI
Prometheus metrics, OpenTelemetry distributed tracing, and Sentry initialization.
"""

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    sentry_sdk = None
    FastApiIntegration = None
    SqlalchemyIntegration = None
    SENTRY_AVAILABLE = False

from fastapi import FastAPI

try:
    from prometheus_client import Counter, Gauge, Histogram
except ImportError:
    class _MockMetric:
        def labels(self, *args, **kwargs): return self
        def inc(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def time(self):
            import contextlib
            return contextlib.nullcontext()
    Counter = Gauge = Histogram = lambda *args, **kwargs: _MockMetric()

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    PROMETHEUS_INSTRUMENTATOR_AVAILABLE = True
except ImportError:
    Instrumentator = None
    PROMETHEUS_INSTRUMENTATOR_AVAILABLE = False

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("codemigration.telemetry")

# Prometheus Metrics Definitions
WORKFLOW_EXECUTION_COUNTER = Counter(
    "codemigration_workflows_total",
    "Total number of migration and refactoring workflows started",
    ["workflow_type", "status", "target_framework"],
)

WORKFLOW_DURATION_HISTOGRAM = Histogram(
    "codemigration_workflow_duration_seconds",
    "Time spent executing complete workflows or agent steps",
    ["workflow_type", "step_name"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800),
)

LLM_TOKEN_USAGE_COUNTER = Counter(
    "codemigration_llm_tokens_total",
    "Total LLM tokens consumed by agent operations",
    ["provider", "model", "token_type"], # prompt or completion
)

LLM_COST_COUNTER = Counter(
    "codemigration_llm_cost_usd_total",
    "Total estimated cost in USD for LLM invocations",
    ["provider", "model"],
)

AST_PARSE_DURATION_HISTOGRAM = Histogram(
    "codemigration_ast_parse_duration_seconds",
    "Time spent parsing files into Tree-sitter AST and Graph",
    ["language"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
)

ACTIVE_WORKFLOWS_GAUGE = Gauge(
    "codemigration_active_workflows",
    "Currently active and running migration workflows",
)


def init_telemetry(app: FastAPI) -> None:
    """Initialize OpenTelemetry, Prometheus metrics endpoint, and Sentry error tracking."""
    # 1. Prometheus Instrumentator
    if settings.ENABLE_TELEMETRY and PROMETHEUS_INSTRUMENTATOR_AVAILABLE and Instrumentator:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
        logger.info("Prometheus metrics initialized at /metrics")

    # 2. OpenTelemetry Distributed Tracing
    if settings.ENABLE_TELEMETRY and settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource(attributes={"service.name": settings.PROJECT_NAME.lower().replace(" ", "-")})
            tracer_provider = TracerProvider(resource=resource)
            otlp_exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            trace.set_tracer_provider(tracer_provider)
            logger.info("OpenTelemetry TracerProvider initialized", endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        except ImportError as e:
            logger.warning("OpenTelemetry SDK not fully installed; tracing disabled", error=str(e))
        except Exception as e:
            logger.warning("Failed to initialize OTel TracerProvider", error=str(e))

    # 3. Sentry Error Tracking
    if settings.SENTRY_DSN and SENTRY_AVAILABLE and sentry_sdk:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=1.0 if settings.DEBUG else 0.1,
            integrations=[
                FastApiIntegration(),  # type: ignore
                SqlalchemyIntegration(),  # type: ignore
            ],
        )
        logger.info("Sentry error tracking initialized")
