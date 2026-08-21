"""Structured logging setup (structlog), configured once at app startup
(app.main calls configure_logging() before creating the FastAPI app) so
every logger.bind()/logger.info() call anywhere in the app shares one
processor pipeline, not per-module ad hoc setup.

Console-rendered (human-readable key=value pairs), not JSON: the primary
reader is still a developer's terminal, not a machine. Every event is
also teed to the OTel logs pipeline (-> collector -> Loki, see
app.core.otel_config and observability/README.md), rendered via
structlog's own KeyValueRenderer (quoted values, e.g. trace_id='abc...')
-- Grafana's Loki derived-field regex
(observability/grafana/provisioning/datasources/datasources.yaml) is
written to match that exact quoted shape, not the terminal's.

Deliberately standalone (structlog.PrintLoggerFactory(), not routed
through Python's stdlib `logging`): keeps this additive -- uvicorn's own
access/error logs are untouched, nothing here can interact with or
break their existing configuration. The OTel tee uses its own,
non-propagating stdlib logger (OTEL_LOG_LOGGER_NAME) purely as an export
sink, not a rerouting of this pipeline through stdlib logging.
"""
import logging

import structlog
from opentelemetry import trace

from app.core.otel_config import OTEL_LOG_LOGGER_NAME


def _inject_trace_context(logger, method_name, event_dict):
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


_KV_RENDERER = structlog.processors.KeyValueRenderer()


def _export_to_otel(logger, method_name, event_dict):
    # Reads event_dict["level"] (already normalized by add_log_level,
    # earlier in this pipeline -- e.g. "exception" -> "error"), not the
    # raw method_name: stdlib logging has no EXCEPTION level, so deriving
    # from method_name directly would downgrade every logger.exception()
    # call to INFO here.
    level = getattr(logging, event_dict.get("level", "info").upper(), logging.INFO)
    rendered = _KV_RENDERER(logger, method_name, event_dict)
    logging.getLogger(OTEL_LOG_LOGGER_NAME).log(level, rendered)
    return event_dict


def configure_logging() -> None:
    # A NullHandler up front means log calls are silently dropped, not
    # routed to Python's stderr "handler of last resort", in the narrow
    # window before configure_otel() (app.main) attaches the real OTLP
    # handler.
    logging.getLogger(OTEL_LOG_LOGGER_NAME).addHandler(logging.NullHandler())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            _inject_trace_context,
            _export_to_otel,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
