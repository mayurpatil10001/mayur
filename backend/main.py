"""
backend/main.py
===============
Uvicorn application entrypoint.
"""

from backend.api.app import create_app
from backend.core.config import settings

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD and not settings.is_production,
        workers=1 if settings.RELOAD else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=False,  # Handled by our middleware
    )
