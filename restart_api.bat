@echo off
echo Restarting Trading Platform API Server...
echo.

REM Kill any existing uvicorn processes
taskkill /f /im python.exe 2>nul

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start the API server
echo Starting API server on port 8000...
python -m uvicorn trading_platform.api.main:app --reload --host 0.0.0.0 --port 8000

pause