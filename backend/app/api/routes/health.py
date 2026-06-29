"""Health / readiness endpoints.

These let you (and later, Docker / a load balancer) verify the service is up
without touching the database or camera. Phase 1 ships only this router.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app import __version__
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
def health() -> dict:
    """Return basic service status. Always cheap and dependency-free."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": __version__,
        "environment": settings.ENVIRONMENT,
        "time": datetime.now(timezone.utc).isoformat(),
    }
