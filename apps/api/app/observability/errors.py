import logging

logger = logging.getLogger(__name__)


def record_exception(
    error: Exception,
    *,
    operation: str,
    context: dict[str, object] | None = None,
) -> None:
    """Record an application error with structured operational context."""
    logger.error(
        "application_error",
        exc_info=error,
        extra={
            "observability": {
                "operation": operation,
                **(context or {}),
            },
        },
    )
