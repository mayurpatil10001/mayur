from fastapi import FastAPI, HTTPException, Request, Body, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any, Optional

from ..config import config
from .routers import accounts, trades, analytics, recommendations, data_ingestion, auth, health, time_bin_analytics, exports, advanced_recommendations, system, analysis, trade_import, account_management, backtesting, vix_regime
from .dependencies import get_database_session, get_service_container
from .middleware import LoggingMiddleware, ErrorHandlingMiddleware, SecurityHeadersMiddleware, RateLimitMiddleware, MonitoringMiddleware
from .exceptions import TradingPlatformException


from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(config.LOG_FILE, maxBytes=50*1024*1024, backupCount=5),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("Starting Trading Optimization Platform API (Streamlined)")
    
    # Validate paths without blocking
    try:
        if not config.validate_paths():
            logger.warning("Some SierraChart paths are not accessible")
    except Exception as e:
        logger.error(f"Config validation error: {e}")
    
    logger.info("API startup sequence completed (services on-demand)")
    
    yield
    
    logger.info("Shutting down Trading Optimization Platform API")
    logger.info("API shutdown completed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="Trading Optimization Platform API",
        description="""
        A comprehensive REST API for analyzing historical trading data and generating
        optimized trading recommendations using statistical analysis, machine learning,
        and Monte Carlo simulations.
        
        ## Features
        
        * **Data Ingestion**: Import and process SierraChart trading data
        * **Analytics**: Statistical analysis and performance metrics
        * **Machine Learning**: Predictive models with walk-forward analysis
        * **Monte Carlo**: Risk assessment and scenario simulation
        * **Recommendations**: Intelligent trading suggestions
        * **Account Management**: Multi-account and multi-asset support
        
        ## Authentication
        
        This API uses JWT-based authentication. Include your token in the
        Authorization header: `Bearer <your-token>`
        """,
        version="1.0.0",
        contact={
            "name": "Trading Platform Support",
            "email": "support@tradingplatform.com",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add security scheme to OpenAPI
    app.openapi_schema = None  # Reset to regenerate with security
    
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        from fastapi.openapi.utils import get_openapi
        
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            contact=app.contact,
            license_info=app.license_info
        )
        
        # Ensure components section exists
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        
        # Add security scheme
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token authentication"
            }
        }
        
        # Add security requirement to all endpoints except health, docs, and auth
        for path_name, path in openapi_schema["paths"].items():
            # Skip health endpoint, docs endpoints, and auth endpoints
            if path_name in ["/health", "/docs", "/redoc", "/openapi.json"] or path_name.startswith("/api/v1/auth"):
                continue
                
            for method in path.values():
                if isinstance(method, dict) and "security" not in method:
                    method["security"] = [{"BearerAuth": []}]
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    # Add middleware
    setup_middleware(app)
    
    # Add exception handlers
    setup_exception_handlers(app)
    
    # Include routers
    setup_routers(app)
    
    return app


def setup_middleware(app: FastAPI) -> None:
    """Configure application middleware."""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development
        allow_credentials=False,  # Set to False when using allow_origins=["*"]
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", config.API_HOST, "testserver"]
    )
    
    # Custom middleware (order matters - rate limiting should be early)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=getattr(config, 'RATE_LIMIT_PER_MINUTE', 60))
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MonitoringMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers."""
    
    @app.exception_handler(TradingPlatformException)
    async def trading_platform_exception_handler(request: Request, exc: TradingPlatformException):
        """Handle custom trading platform exceptions."""
        logger.error(f"Trading platform error: {exc.message} - {exc.details}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_type,
                "message": exc.message,
                "details": exc.details,
                "timestamp": time.time()
            }
        )
    
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        """Handle 404 Not Found errors with consistent format."""
        logger.warning(f"404 Not Found: {request.url.path}")
        
        return JSONResponse(
            status_code=404,
            content={
                "error": "NOT_FOUND",
                "message": "The requested resource was not found",
                "status_code": 404,
                "timestamp": time.time(),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with consistent format."""
        logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
        
        # Map status codes to error types
        error_type_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_SERVER_ERROR"
        }
        
        error_type = error_type_map.get(exc.status_code, "HTTP_ERROR")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error_type,
                "message": str(exc.detail),
                "status_code": exc.status_code,
                "timestamp": time.time(),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "timestamp": time.time()
            }
        )


def setup_routers(app: FastAPI) -> None:
    """Configure API routers."""
    
    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint."""
        import sqlite3
        from pathlib import Path
        
        db_status = "disconnected"
        db_info = {}
        
        try:
            db_path = Path("trading_platform.db")
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Get table count
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # Get total trades
                cursor.execute("SELECT COUNT(*) FROM processed_trades")
                total_trades = cursor.fetchone()[0]
                
                # Get unique accounts
                cursor.execute("""
                    SELECT COUNT(DISTINCT account_name) 
                    FROM processed_trades 
                """)
                unique_accounts = cursor.fetchone()[0]
                
                conn.close()
                
                db_status = "connected"
                db_info = {
                    "tables": table_count,
                    "total_trades": total_trades,
                    "unique_accounts": unique_accounts,
                    "db_path": str(db_path.absolute())
                }
            else:
                db_status = "file_not_found"
                db_info = {"db_path": str(db_path.absolute())}
                
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "timestamp": time.time(),
            "version": "1.0.0",
            "database": db_status,
            "database_info": db_info,
            "services": "operational"
        }
    
    # Add OPTIONS handler for CORS preflight
    @app.options("/health", tags=["Health"])
    async def health_options():
        """Handle CORS preflight for health endpoint."""
        return {"message": "OK"}
    
    # Include authentication router (no auth required)
    app.include_router(
        auth.router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    
    # Include feature routers (auth required)
    # Include configuration-heavy routers first to avoid shadowing by generic ID routes
    app.include_router(
        trade_import.router,
        prefix="/api/v1/trades",
        tags=["Trade Import"]
    )
    
    app.include_router(
        account_management.router,
        prefix="/api/v1/accounts",
        tags=["Account Management"]
    )

    app.include_router(
        accounts.router,
        prefix="/api/v1/accounts",
        tags=["Accounts"]
    )
    
    app.include_router(
        trades.router,
        prefix="/api/v1/trades",
        tags=["Trades"]
    )
    
    app.include_router(
        analytics.router,
        prefix="/api/v1/analytics",
        tags=["Analytics"]
    )
    
    app.include_router(
        recommendations.router,
        prefix="/api/v1/recommendations",
        tags=["Recommendations"]
    )
    
    app.include_router(
        data_ingestion.router,
        prefix="/api/v1/data",
        tags=["Data Ingestion"]
    )
    
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["Health & Monitoring"]
    )
    
    app.include_router(
        time_bin_analytics.router,
        prefix="/api/v1/time-bins",
        tags=["Time-Bin Analytics"]
    )
    
    app.include_router(
        exports.router,
        prefix="/api/v1/exports",
        tags=["Data Export"]
    )
    
    app.include_router(
        advanced_recommendations.router,
        prefix="/api/v1/recommendations",
        tags=["Advanced Recommendations"]
    )
    
    app.include_router(
        trade_import.router,
        prefix="/api/v1/trade-import",
        tags=["Trade Import"]
    )
    
    app.include_router(
        system.router,
        tags=["System Monitoring"]
    )
    
    app.include_router(
        analysis.router,
        tags=["Analysis Jobs"]
    )
    
    # Backtesting router — mounted at /api/backtesting (NOT under /api/v1)
    # to match the frontend expectation: POST /api/backtesting/run
    app.include_router(
        backtesting.router,
        prefix="/api/backtesting",
        tags=["Backtesting"]
    )
    
    app.include_router(
        vix_regime.router,
        prefix="/api/vix-regime",
        tags=["VIX Regime"]
    )


# Create the application instance
app = create_app()


# System endpoints are handled in routers/system.py

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "trading_platform.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD,
        log_level=config.LOG_LEVEL.lower()
    ) 
 
