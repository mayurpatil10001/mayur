"""
backend/api/v1/router.py
========================
Aggregates all v1 route modules into a single router.
"""

from fastapi import APIRouter

from backend.api.v1.routes import (
    analytics,
    ingestion,
    recommendations,
    trades,
    walkforward,
)

v1_router = APIRouter()

v1_router.include_router(trades.router, prefix="/trades", tags=["Trades"])
v1_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
v1_router.include_router(walkforward.router, prefix="/walkforward", tags=["Walk-Forward"])
v1_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
v1_router.include_router(ingestion.router, prefix="/ingest", tags=["Ingestion"])
