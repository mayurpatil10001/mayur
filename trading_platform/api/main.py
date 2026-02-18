"""
Main FastAPI application setup with routing and middleware configuration.

This module sets up the FastAPI application with proper routing,
dependency injection, middleware, and documentation.

Requirements: 10.1, 10.4
"""

from fastapi import FastAPI, HTTPException, Request, Body, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any, Optional

from ..config import config
from .routers import accounts, trades, analytics, recommendations, data_ingestion, auth, health, time_bin_analytics, exports, advanced_recommendations, system, analysis, trade_import, account_management
from .dependencies import get_database_session, get_service_container
from .middleware import LoggingMiddleware, ErrorHandlingMiddleware, SecurityHeadersMiddleware, RateLimitMiddleware, MonitoringMiddleware
from .exceptions import TradingPlatformException


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Trading Optimization Platform API")
    
    # Initialize database connection
    try:
        db_session = get_database_session()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to establish database connection: {e}")
        raise
    
    # Initialize service container
    try:
        service_container = get_service_container()
        logger.info("Service container initialized")
    except Exception as e:
        logger.error(f"Failed to initialize service container: {e}")
        raise
    
    # Validate configuration
    if not config.validate_paths():
        logger.warning("Some SierraChart paths are not accessible")
    
    logger.info("API startup completed successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Trading Optimization Platform API")
    
    # Close database connections
    try:
        if 'db_session' in locals():
            db_session.close()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
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
        system.router,
        tags=["System Monitoring"]
    )
    
    app.include_router(
        analysis.router,
        tags=["Analysis Jobs"]
    )


# Create the application instance
app = create_app()


@app.post("/api/system/check-path")
async def check_path(request: dict = Body(...)):
    try:
        import glob
        import os
        import re
        import datetime
        from trading_platform.services.settings import settings_service

        path = request.get("path", "")
        target_symbol = request.get("symbol", "").upper()
        # Respect saved lookback days if available
        settings = settings_service.get_settings()
        try:
            days_limit = int(settings.get("import_days", 30))
        except:
            days_limit = 30
            
        cutoff_time = (datetime.datetime.now() - datetime.timedelta(days=days_limit)).timestamp() if days_limit > 0 else 0
        
        if not path:
            return {"exists": False, "files": [], "message": "No path provided"}
            
        clean_path = os.path.normpath(path)
        if not os.path.exists(clean_path):
            return {"exists": False, "files": [], "message": f"Path not found: {clean_path}"}
            
        if not os.path.isdir(clean_path):
            return {"exists": True, "files": [], "message": "Path is not a directory"}
            
        all_files_raw = glob.glob(os.path.join(clean_path, "*.txt")) + \
                        glob.glob(os.path.join(clean_path, "*.log")) + \
                        glob.glob(os.path.join(clean_path, "*.data"))
        
        # Filter by date
        all_files = [f for f in all_files_raw if os.path.getmtime(f) >= cutoff_time]
        
        if not all_files:
            msg = f"No log files found in last {days_limit} days" if days_limit > 0 else "No log files found in directory"
            return {"exists": True, "files": [], "count": 0, "accounts": [], "message": msg}

        # Group files by account
        account_files = {}
        for f in all_files:
            try:
                fname = os.path.basename(f)
                parts = fname.split('.')
                if len(parts) > 1:
                    account = parts[-2].upper()
                    account = re.sub(r'_UTC$', '', account)
                    if account not in account_files:
                        account_files[account] = []
                    account_files[account].append(f)
            except: pass

        # Filter accounts by target_symbol
        detected_accounts = []
        
        for account, files in account_files.items():
            # If no symbol filter, include all
            if not target_symbol:
                detected_accounts.append(account)
                continue
                
            match_found = False
            # 1. Filename match
            for f in files:
                if target_symbol in os.path.basename(f).upper():
                    match_found = True
                    break
            if match_found:
                detected_accounts.append(account)
                continue
                
            # 2. Account name match
            if account.upper().startswith(target_symbol):
                detected_accounts.append(account)
                continue
                
            # 3. Content Peek (Last 10 files)
            try:
                files.sort(key=os.path.getmtime, reverse=True)
                recent_files = files[:10]
                
                found_in_history = False
                for recent_file in recent_files:
                    try:
                        file_size = os.path.getsize(recent_file)
                        if file_size > 0:
                            data = b""
                            with open(recent_file, "rb") as bf:
                                # Read first 100KB
                                data += bf.read(100 * 1024)
                                # If file is large, also read the last 200KB where recent trades are
                                if file_size > 300 * 1024:
                                    bf.seek(file_size - (200 * 1024))
                                    data += bf.read()
                                elif file_size > 100 * 1024:
                                    # Just read the rest
                                    data += bf.read()
                                
                                # Check patterns - Case insensitive
                                uppercase_data = data.upper()
                                
                                # pattern_a: match symbol + month code + year (e.g. NQH24)
                                pattern_a = rb'\b' + target_symbol.encode() + rb'[FGHJKMNQUVXZ]\d{1,2}\b'
                                # pattern_b: match Symbol: NQ or Contract: NQ
                                pattern_b = rb'(?:SYMBOL|CONTRACT|SIMULATED)[:\s]+' + target_symbol.encode() + rb'\b'
                                # pattern_c: just find the symbol string if it's a text log
                                pattern_c = target_symbol.encode() + rb'\b'
                                
                                if re.search(pattern_a, uppercase_data) or \
                                   re.search(pattern_b, uppercase_data) or \
                                   re.search(pattern_c, uppercase_data):
                                    found_in_history = True
                                    break
                    except: pass
                
                if found_in_history:
                    detected_accounts.append(account)
            except: pass

        # Final Sort and Return
        try:
            all_logs = sorted(all_files, key=os.path.getmtime, reverse=True)
            file_list = [os.path.basename(f) for f in all_logs[:5]]
        except:
            file_list = [os.path.basename(f) for f in all_files[:5]]
        
        return {
            "exists": True, 
            "files": file_list, 
            "count": len(all_files),
            "accounts": sorted(detected_accounts),
            "message": f"Found {len(all_files)} files." + (f" Showing accounts with '{target_symbol}'." if target_symbol else "")
        }
        
    except Exception as e:
        print(f"Check Path Fatal Error: {e}")
        return {"exists": False, "files": [], "message": f"Scan Failed: {str(e)}"}

# --- Import Control Endpoints ---
from trading_platform.services.binary_log_parser import importer, BinaryLogParser

@app.post("/api/system/import-start")
async def start_import(background_tasks: BackgroundTasks, request: dict = Body(...)):
    if importer.running:
        return {"message": "Import already running", "running": True}
        
    paths = request.get("paths", [])
    symbol = request.get("symbol", None)
    accounts = request.get("accounts", None) 
    
    from trading_platform.services.settings import settings_service
    settings = settings_service.get_settings()
    try:
        days = int(request.get("days", settings.get("import_days", 30)))
    except:
        days = 30
    
    if not paths:
        return {"message": "No paths provided, checking defaults...", "running": False}
        
    # Start background task with optional filters
    background_tasks.add_task(importer.run_import, paths, symbol, accounts, days_lookback=days)
    return {"message": f"Import started{' for ' + str(accounts) if accounts else ''} (Last {days} days)", "running": True}

@app.post("/api/system/import-stop")
async def stop_import():
    importer.stop()
    return {"message": "Stopping import...", "running": False}

@app.get("/api/system/import-status")
async def get_import_status():
    return {
        "running": importer.running,
        "message": importer.message,
        "progress": importer.progress,
        "stats": f"Processed: {importer.stats.get('processed', 0)} | Found: {importer.stats.get('found', 0)}",
        "details": importer.stats.get("summaries", {})
    }


@app.post("/api/system/purge-anomalies")
async def purge_anomalies(request: dict = Body(...)):
    account = request.get("account")
    symbol = request.get("symbol")
    if not account:
        raise HTTPException(status_code=400, detail="Account required")
    
    # Enable purge_overnight to actually delete the identified overnight trades
    res = importer.purge_anomalies(account, symbol, purge_overnight=True)
    return {"message": "Data cleaned successfully", "removed": res}

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "trading_platform.api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD,
        log_level=config.LOG_LEVEL.lower()
    )