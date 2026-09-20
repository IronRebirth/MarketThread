import secrets
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestTrace:
    trace_id: str
    span_id: str


_current_trace: ContextVar[RequestTrace | None] = ContextVar(
    "marketthread_request_trace",
    default=None,
)


def generate_trace() -> RequestTrace:
    return RequestTrace(
        trace_id=secrets.token_hex(16),
        span_id=secrets.token_hex(8),
    )


def parse_traceparent(value: str | None) -> RequestTrace | None:
    if not value:
        return None

    parts = value.split("-")

    if len(parts) != 4:
        return None

    version, trace_id, parent_span_id, flags = parts

    if version != "00" or len(trace_id) != 32 or len(parent_span_id) != 16:
        return None

    try:
        int(trace_id, 16)
        int(parent_span_id, 16)
        int(flags, 16)
    except ValueError:
        return None

    if trace_id == "0" * 32 or parent_span_id == "0" * 16:
        return None

    return RequestTrace(trace_id=trace_id, span_id=secrets.token_hex(8))


def set_current_trace(trace: RequestTrace):
    return _current_trace.set(trace)


def reset_current_trace(token) -> None:
    _current_trace.reset(token)


def get_current_trace() -> RequestTrace | None:
    return _current_trace.get()


def traceparent_header(trace: RequestTrace) -> str:
    return f"00-{trace.trace_id}-{trace.span_id}-01"
