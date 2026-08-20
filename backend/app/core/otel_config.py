"""OpenTelemetry setup: traces, metrics, and a log-export bridge, all
shipped over one OTLP/gRPC connection to the collector (see
observability/README.md for the receiving side). Mirrors
logging_config.py's shape -- one configure_otel() called once at app
startup, before anything it instruments runs.

Exporters retry/back off silently if the collector isn't reachable
(`make observability-up` brings it up) -- same posture as
OPENAI_BASE_URL: nothing here is required for the app to work.
"""
import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings

# A dedicated, non-propagating stdlib logger used purely as the OTel export
# sink -- logging_config.py's structlog pipeline tees every event here in
# addition to rendering it to the console. Never touches the root logger
# or uvicorn's own loggers (propagate=False), keeping this additive, same
# principle logging_config.py already documents for its own setup.
OTEL_LOG_LOGGER_NAME = "ludora.otel_export"


def configure_otel() -> None:
    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME,
        "deployment.environment": "local",
    })
    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True))
        ],
    )
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True))
    )
    otel_log_logger = logging.getLogger(OTEL_LOG_LOGGER_NAME)
    otel_log_logger.setLevel(logging.INFO)
    otel_log_logger.propagate = False
    otel_log_logger.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))

    # httpx backs the openai SDK calls in assistant_service.py/
    # summarization_service.py -- global instrumentation, no client
    # instance to pass in. FastAPI is instrumented separately in main.py
    # (needs the `app` instance) and SQLAlchemy in database/session.py
    # (needs the `engine` instance), both created after this module loads.
    HTTPXClientInstrumentor().instrument()
