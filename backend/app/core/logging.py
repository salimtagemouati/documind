"""
Structured logging using structlog.
In development: pretty colored output.
In production: JSON lines (ideal for Datadog / Loki / CloudWatch ingestion).
"""
import logging
import sys

import structlog
from app.core.config import get_settings

settings = get_settings()


def configure_logging() -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.ENVIRONMENT == "production":
        # JSON output for log aggregators
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable colored output for local dev
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Silence noisy third-party loggers in production
    for name in ["uvicorn.access", "httpx", "httpcore"]:
        logging.getLogger(name).setLevel(
            logging.WARNING if settings.ENVIRONMENT == "production" else logging.INFO
        )


def get_logger(name: str = __name__):
    return structlog.get_logger(name)
