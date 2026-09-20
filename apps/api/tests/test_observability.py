import json
import logging

from httpx import AsyncClient

from app.observability.metrics import (
    REQUEST_DURATION_SECONDS,
    REQUESTS_TOTAL,
    render_prometheus,
)
from app.observability.tracing import parse_traceparent


def test_traceparent_is_validated_and_normalized() -> None:
    trace = parse_traceparent(
        "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
    )

    assert trace is not None
    assert trace.trace_id == "0123456789abcdef0123456789abcdef"
    assert trace.span_id != "0123456789abcdef"


def test_invalid_traceparent_is_rejected() -> None:
    assert parse_traceparent("not-a-trace") is None
    assert (
        parse_traceparent(
            "00-00000000000000000000000000000000-0123456789abcdef-01",
        )
        is None
    )


def test_metrics_are_rendered_as_prometheus() -> None:
    REQUESTS_TOTAL.inc(("GET", "/test", "200"))
    REQUEST_DURATION_SECONDS.observe(("GET", "/test"), 0.125)

    rendered = render_prometheus().decode("utf-8")

    assert "marketthread_http_requests_total" in rendered
    assert 'method="GET"' in rendered
    assert "marketthread_http_request_duration_seconds_bucket" in rendered
    assert "marketthread_http_request_duration_seconds_count" in rendered


def test_structured_log_formatter_includes_trace_context(caplog) -> None:
    from app.observability.logging import JsonFormatter
    from app.observability.tracing import (
        generate_trace,
        reset_current_trace,
        set_current_trace,
    )

    token = set_current_trace(generate_trace())

    try:
        record = logging.LogRecord(
            "test",
            logging.INFO,
            __file__,
            1,
            "hello",
            (),
            None,
        )
        rendered = JsonFormatter().format(record)
    finally:
        reset_current_trace(token)

    payload = json.loads(rendered)

    assert payload["message"] == "hello"
    assert len(payload["trace_id"]) == 32
    assert len(payload["span_id"]) == 16


async def test_metrics_endpoint(client: AsyncClient) -> None:
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "marketthread_http_requests_total" in response.text
