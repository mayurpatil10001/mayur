"""
backend/api/app.py
==================
FastAPI application factory with lifespan, middleware, exception handlers,
and OpenAPI metadata for the SC Trade Optimization Platform.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.core.config import settings
from backend.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle handler."""
    # ── Startup ──
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENV}]")

    # Initialize database
    from backend.db.session import engine
    from backend.db.base import Base

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)

    # Initialize Sentry (production only)
    if settings.SENTRY_DSN and settings.is_production:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
            logger.info("Sentry initialized.")
        except ImportError:
            logger.warning("sentry-sdk not installed — Sentry disabled.")

    yield

    # ── Shutdown ──
    from backend.db.session import close_db
    await close_db()
    logger.info("Application shutdown complete.")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
## Sierra Chart Trade Optimization Platform API

End-to-end trading analytics platform with:
- **Binary log parsing** with Ghost Fill Resynchronization Engine (GFRE)
- **BH-FDR multi-testing gate** for time-slot promotion
- **Walk-forward validation** with rolling IS/OOS windows
- **Monte Carlo simulation** (10,000 paths, ruin probability)
- **Strategy recommendations** ranked by Sharpe/Expectancy

### Authentication
All endpoints require `X-API-Key` header in production.
Set `API_KEY` in `.env` (empty string disables auth in development).
        """.strip(),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # ── Request logging + timing middleware ───────────────────────────────────
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Attach request ID for downstream logging
        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration_ms:.1f}ms"

        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} "
            f"[{duration_ms:.1f}ms] req={request_id}"
        )
        return response

    # ── Global exception handlers ─────────────────────────────────────────────
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "type": "value_error"},
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "type": "file_not_found"},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error. Please check server logs.",
                "type": type(exc).__name__,
            },
        )

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.get("/health", tags=["System"], summary="Health check")
    async def health_check() -> dict[str, Any]:
        from backend.db.session import check_db_health
        db_health = await check_db_health()
        return {
            "status": "healthy" if db_health["status"] == "healthy" else "degraded",
            "version": settings.APP_VERSION,
            "environment": settings.ENV,
            "database": db_health,
        }

    # ── Mount v1 router ───────────────────────────────────────────────────────
    from backend.api.v1.router import v1_router
    app.include_router(v1_router, prefix="/api/v1")

    return app
