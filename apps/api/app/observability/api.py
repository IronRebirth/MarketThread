from fastapi import APIRouter
from fastapi.responses import Response

from .metrics import render_prometheus

router = APIRouter(tags=["system"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose application metrics in Prometheus text format."""
    return Response(
        content=render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )
