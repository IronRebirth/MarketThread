import logging
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .logging import configure_logging
from .metrics import (
    REQUEST_DURATION_SECONDS,
    REQUEST_ERRORS_TOTAL,
    REQUESTS_TOTAL,
)
from .tracing import (
    generate_trace,
    parse_traceparent,
    reset_current_trace,
    set_current_trace,
    traceparent_header,
)

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Attach trace context, structured request logs, and HTTP metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        started = perf_counter()
        trace = parse_traceparent(request.headers.get("traceparent")) or generate_trace()
        token = set_current_trace(trace)
        response: Response | None = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            REQUEST_ERRORS_TOTAL.inc(
                (request.method, _route_label(request)),
            )
            logger.exception(
                "http_request_failed",
                extra={
                    "observability": {
                        "method": request.method,
                        "path": request.url.path,
                    },
                },
            )
            raise
        finally:
            duration = perf_counter() - started
            route = _route_label(request)

            REQUESTS_TOTAL.inc(
                (request.method, route, str(status_code)),
            )
            REQUEST_DURATION_SECONDS.observe(
                (request.method, route),
                duration,
            )

            logger.info(
                "http_request_completed",
                extra={
                    "observability": {
                        "method": request.method,
                        "path": request.url.path,
                        "route": route,
                        "status_code": status_code,
                        "duration_seconds": round(duration, 6),
                    },
                },
            )

            if response is not None:
                response.headers["X-Request-ID"] = trace.trace_id
                response.headers["traceparent"] = traceparent_header(trace)

            reset_current_trace(token)


def _route_label(request: Request) -> str:
    route = request.scope.get("route")

    if route is not None:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            return path

    return "unmatched"
