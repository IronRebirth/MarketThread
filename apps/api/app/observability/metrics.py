from collections.abc import Iterable
from threading import Lock


class _Counter:
    def __init__(self, name: str, help_text: str, labels: tuple[str, ...]) -> None:
        self.name = name
        self.help_text = help_text
        self.labels = labels
        self.values: dict[tuple[str, ...], float] = {}

    def inc(self, values: tuple[str, ...], amount: float = 1.0) -> None:
        with _lock:
            self.values[values] = self.values.get(values, 0.0) + amount


class _Histogram:
    def __init__(
        self,
        name: str,
        help_text: str,
        labels: tuple[str, ...],
        buckets: tuple[float, ...],
    ) -> None:
        self.name = name
        self.help_text = help_text
        self.labels = labels
        self.buckets = buckets
        self.values: dict[tuple[str, ...], list[float]] = {}
        self.counts: dict[tuple[str, ...], list[int]] = {}
        self.totals: dict[tuple[str, ...], tuple[float, int]] = {}

    def observe(self, values: tuple[str, ...], amount: float) -> None:
        with _lock:
            self.values.setdefault(values, []).append(amount)
        bucket_counts = self.counts.setdefault(
            values,
            [0] * (len(self.buckets) + 1),
        )

        for index, bucket in enumerate(self.buckets):
            if amount <= bucket:
                bucket_counts[index] += 1

        bucket_counts[-1] += 1
        total, count = self.totals.get(values, (0.0, 0))
        self.totals[values] = (total + amount, count + 1)


_lock = Lock()
_counters: dict[str, _Counter] = {}
_histograms: dict[str, _Histogram] = {}


def counter(
    name: str,
    help_text: str,
    labels: Iterable[str] = (),
) -> _Counter:
    label_tuple = tuple(labels)
    with _lock:
        metric = _counters.get(name)
        if metric is None:
            metric = _Counter(name, help_text, label_tuple)
            _counters[name] = metric
        return metric


def histogram(
    name: str,
    help_text: str,
    labels: Iterable[str] = (),
    buckets: Iterable[float] = (),
) -> _Histogram:
    label_tuple = tuple(labels)
    bucket_tuple = tuple(buckets)
    with _lock:
        metric = _histograms.get(name)
        if metric is None:
            metric = _Histogram(name, help_text, label_tuple, bucket_tuple)
            _histograms[name] = metric
        return metric


REQUESTS_TOTAL = counter(
    "marketthread_http_requests_total",
    "Total HTTP requests handled by the API.",
    ("method", "route", "status"),
)
REQUEST_ERRORS_TOTAL = counter(
    "marketthread_http_errors_total",
    "Total HTTP 5xx responses and unhandled request exceptions.",
    ("method", "route"),
)
REQUEST_DURATION_SECONDS = histogram(
    "marketthread_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
    (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
JOB_STARTED_TOTAL = counter(
    "marketthread_jobs_started_total",
    "Total background jobs started through the observability hook.",
    ("job_name",),
)
JOB_COMPLETED_TOTAL = counter(
    "marketthread_jobs_completed_total",
    "Total background jobs completed through the observability hook.",
    ("job_name", "status"),
)
PROVIDER_REQUESTS_TOTAL = counter(
    "marketthread_provider_requests_total",
    "Total external provider calls observed by MarketThread.",
    ("provider", "operation", "status"),
)
PROVIDER_DURATION_SECONDS = histogram(
    "marketthread_provider_request_duration_seconds",
    "External provider request duration in seconds.",
    ("provider", "operation"),
    (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)


def render_prometheus() -> bytes:
    lines: list[str] = []

    with _lock:
        counters = tuple(_counters.values())
        histograms = tuple(_histograms.values())

        for metric in counters:
            lines.append(f"# HELP {metric.name} {metric.help_text}")
            lines.append(f"# TYPE {metric.name} counter")
            for label_values, value in sorted(metric.values.items()):
                lines.append(
                    f"{metric.name}{_render_labels(metric.labels, label_values)} {value}",
                )

        for metric in histograms:
            lines.append(f"# HELP {metric.name} {metric.help_text}")
            lines.append(f"# TYPE {metric.name} histogram")
            for label_values in sorted(metric.counts):
                counts = metric.counts[label_values]
                for index, bucket in enumerate(metric.buckets):
                    labels = metric.labels + ("le",)
                    values = label_values + (str(bucket),)
                    lines.append(
                        f"{metric.name}_bucket{_render_labels(labels, values)} "
                        f"{counts[index]}",
                    )

                total, count = metric.totals[label_values]
                labels = metric.labels + ("le",)
                values = label_values + ("+Inf",)
                lines.append(
                    f"{metric.name}_bucket{_render_labels(labels, values)} {count}",
                )
                lines.append(
                    f"{metric.name}_sum{_render_labels(metric.labels, label_values)} "
                    f"{total}",
                )
                lines.append(
                    f"{metric.name}_count{_render_labels(metric.labels, label_values)} "
                    f"{count}",
                )

    return ("\n".join(lines) + "\n").encode("utf-8")


def _render_labels(
    names: tuple[str, ...],
    values: tuple[str, ...],
) -> str:
    if not names:
        return ""

    pairs = [
        f'{name}="{value.replace(chr(92), chr(92) + chr(92)).replace(chr(34), chr(92) + chr(34))}"'
        for name, value in zip(names, values, strict=True)
    ]
    return "{" + ",".join(pairs) + "}"
