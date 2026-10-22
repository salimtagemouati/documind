from app.core import logging as app_logging


def test_logging_redacts_sensitive_values_recursively():
    sanitizer = getattr(app_logging, "redact_sensitive_data", None)
    assert sanitizer is not None

    event = {
        "event": "provider_failed",
        "api_key": "do-not-leak",
        "error": "request failed; token=do-not-leak-too",
        "nested": {"authorization": "Bearer do-not-leak-three"},
    }
    sanitized = sanitizer(None, None, event)

    serialized = repr(sanitized)
    assert "do-not-leak" not in serialized
    assert sanitized["api_key"] == "[REDACTED]"
