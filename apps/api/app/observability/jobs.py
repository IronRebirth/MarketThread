import logging
from time import perf_counter

from .metrics import JOB_COMPLETED_TOTAL, JOB_STARTED_TOTAL
from .tracing import get_current_trace

logger = logging.getLogger(__name__)


class JobExecution:
    """Track the lifecycle of a background job through logs and metrics."""

    def __init__(self, job_name: str) -> None:
        self.job_name = job_name
        self.started_at = perf_counter()
        self._finished = False

    def __enter__(self) -> "JobExecution":
        JOB_STARTED_TOTAL.inc((self.job_name,))
        logger.info(
            "background_job_started",
            extra={"observability": {"job_name": self.job_name}},
        )
        return self

    def succeed(self) -> None:
        self._finish("success")

    def fail(self, error: Exception) -> None:
        logger.error(
            "background_job_failed",
            exc_info=error,
            extra={
                "observability": {
                    "job_name": self.job_name,
                    "trace_id": (
                        get_current_trace().trace_id
                        if get_current_trace()
                        else None
                    ),
                },
            },
        )
        self._finish("failure")

    def _finish(self, status: str) -> None:
        if self._finished:
            return

        self._finished = True
        JOB_COMPLETED_TOTAL.inc((self.job_name, status))
        logger.info(
            "background_job_finished",
            extra={
                "observability": {
                    "job_name": self.job_name,
                    "status": status,
                    "duration_seconds": round(
                        perf_counter() - self.started_at,
                        6,
                    ),
                },
            },
        )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is None:
            self.succeed()
        elif isinstance(exc_value, Exception):
            self.fail(exc_value)


def track_job(job_name: str) -> JobExecution:
    return JobExecution(job_name)
