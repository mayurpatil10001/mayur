@echo off
echo ========================================
echo   Trading Platform Backend Only
echo ========================================
echo.

REM Kill existing backend processes
echo [1/3] Cleaning up existing backend processes...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1
echo ✅ Backend cleanup complete

REM Rotate logs
if exist "trading_platform.log" (
    echo [1.5/3] Archiving previous log...
    move /y "trading_platform.log" "trading_platform.log.old" >nul 2>&1
    echo ✅ Previous log archived to trading_platform.log.old
)

timeout /t 1 /nobreak >nul

REM Activate virtual environment
echo.
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    echo Make sure you have created a virtual environment with: python -m venv venv
    pause
    exit /b 1
)
echo ✅ Virtual environment activated

REM Check database
echo.
echo [3/3] Checking database and starting backend...
if exist "trading_platform.db" (
    echo ✅ Database found: trading_platform.db
) else (
    echo ❌ WARNING: Database not found. You may need to run data ingestion first.
)

echo.
echo Starting backend API server...
echo Backend URL: http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo Health Check: http://localhost:8000/health
echo.

uvicorn trading_platform.api.main:app --host 0.0.0.0 --port 8000