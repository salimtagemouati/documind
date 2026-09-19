"""
Structured logging using structlog.
In development: pretty colored output.
In production: JSON lines (ideal for Datadog / Loki / CloudWatch ingestion).
"""
import logging
import re
import sys

import structlog

from app.core.config import get_settings

settings = get_settings()

_SENSITIVE_FIELD_NAMES = {
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
}
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token|authorization|password|secret)"
    r"\s*[:=]\s*[^\s,;]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[^\s,;]+")


def _redact_value(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if (
                str(key).lower() in _SENSITIVE_FIELD_NAMES
                or str(key).lower().endswith(("_api_key", "_password", "_secret", "_token"))
            )
            else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_redact_value(item) for item in value)
    if isinstance(value, str):
        redacted = _SENSITIVE_VALUE_PATTERN.sub(r"\1=[REDACTED]", value)
        return _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)
    return value


def redact_sensitive_data(logger, method_name, event_dict):
    """Remove credential-bearing fields and strings before rendering logs."""
    return _redact_value(event_dict)


def configure_logging() -> None:
    # Basic standard logging config to hook into structlog
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        redact_sensitive_data,
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
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Silence noisy third-party loggers in production
    for name in ["uvicorn.access", "httpx", "httpcore"]:
        logging.getLogger(name).setLevel(
            logging.WARNING if settings.ENVIRONMENT == "production" else logging.INFO
        )


def get_logger(name: str = __name__):
    return structlog.get_logger(name)
