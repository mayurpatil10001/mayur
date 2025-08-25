"""
Main entry point for the Trading Optimization Platform.
"""

import uvicorn
from trading_platform.config import config
from trading_platform.utils.logging import app_logger
from trading_platform.api.main import app


if __name__ == "__main__":
    app_logger.info(f"Starting Trading Optimization Platform on {config.API_HOST}:{config.API_PORT}")
    
    # Validate configuration
    if not config.validate_paths():
        app_logger.warning("Some SierraChart data paths are not accessible")
    
    uvicorn.run(
        "trading_platform.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD,
        log_level=config.LOG_LEVEL.lower()
    )