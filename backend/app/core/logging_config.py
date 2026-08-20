"""Structured logging setup (structlog), configured once at app startup
(app.main calls configure_logging() before creating the FastAPI app) so
every logger.bind()/logger.info() call anywhere in the app shares one
processor pipeline, not per-module ad hoc setup.

Console-rendered (human-readable key=value pairs), not JSON: this runs
locally only, with no log shipping/aggregation pipeline behind it (see
docs/limitations.md's "no online feedback loop"), so the priority is a
developer reading these logs directly, not a machine parsing them.
Swapping to JSON for a real deployment is a one-line renderer change
(structlog.processors.JSONRenderer() in place of ConsoleRenderer()),
not a redesign.

Deliberately standalone (structlog.PrintLoggerFactory(), not routed
through Python's stdlib `logging`): keeps this additive -- uvicorn's own
access/error logs are untouched, nothing here can interact with or
break their existing configuration.
"""
import logging

import structlog


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
