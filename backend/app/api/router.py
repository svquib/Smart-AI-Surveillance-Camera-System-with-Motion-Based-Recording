"""Aggregate API router.

Every feature router (auth, cameras, events, alerts, recordings) will be
included here as the project grows. Phase 1 wires only the health router.
"""

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
