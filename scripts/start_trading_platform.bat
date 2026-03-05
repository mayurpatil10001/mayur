@echo off
setlocal
cd /d "%~dp0.."

echo ========================================
echo   Trading Optimization Platform Startup
echo ========================================
echo.

REM Kill any existing processes first
echo [1/5] Cleaning up existing processes...
echo Killing any existing Python/Node processes...

REM Kill Python processes (uvicorn, python)
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1

REM Kill Node processes (npm, node)
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im npm.exe >nul 2>&1

REM Kill any processes using ports 8000 and 3001
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001') do taskkill /f /pid %%a >nul 2>&1

echo ✅ Cleanup complete - all prior connections terminated

REM Rotate logs
if exist "trading_platform.log" (
    echo [1.5/5] Archiving previous log...
    move /y "trading_platform.log" "trading_platform.log.old" >nul 2>&1
    echo ✅ Previous log archived to trading_platform.log.old
)

REM Wait a moment for processes to fully terminate
timeout /t 2 /nobreak >nul

REM Activate virtual environment
echo.
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    echo Make sure you have created a virtual environment with: python -m venv venv
    pause
    exit /b 1
)
echo ✅ Virtual environment activated

REM Check if database exists
echo.
echo [3/5] Checking database...
if exist "trading_platform.db" (
    echo ✅ Database found: trading_platform.db
) else (
    echo ❌ WARNING: Database not found. You may need to run data ingestion first.
)

REM Start backend in a new window
echo.
echo [4/5] Starting backend API server...
echo Backend will run on: http://localhost:8000
echo API docs will be available at: http://localhost:8000/docs
start "Trading Platform Backend" cmd /k "venv\Scripts\activate.bat && uvicorn trading_platform.api.main:app --host 0.0.0.0 --port 8000"

REM Wait a moment for backend to start
echo Waiting 5 seconds for backend to initialize...
timeout /t 5 /nobreak >nul

REM Start frontend in a new window
echo.
echo [5/5] Starting React frontend...
echo Frontend will run on: http://localhost:3001
cd frontend
start "Trading Platform Frontend" cmd /k "npm start"
cd ..

echo.
echo ========================================
echo   🚀 STARTUP COMPLETE!
echo ========================================
echo.
echo Your trading platform is starting up:
echo.
echo 📊 Backend API:     http://localhost:8000
echo 📋 API Docs:       http://localhost:8000/docs  
echo 🌐 Frontend:       http://localhost:3001
echo 📈 Simple Dashboard: working_dashboard.html (open in browser)
echo.
echo ⚠️  IMPORTANT NOTES:
echo - Both backend and frontend will open in separate windows
echo - Wait for "compiled successfully" message in frontend window
echo - If you see CORS errors, the backend may still be starting
echo - Check the separate windows if something isn't working
echo.
echo Press any key to exit this startup script...
pause >nul