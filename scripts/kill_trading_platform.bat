@echo off
echo ========================================
echo   Stopping Trading Platform
echo ========================================
echo.

echo Terminating all trading platform processes...

REM Kill Python processes (backend)
echo Stopping backend processes...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1

REM Kill Node processes (frontend)
echo Stopping frontend processes...
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im npm.exe >nul 2>&1

REM Kill any processes using our ports
echo Freeing up ports 8000 and 3001...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    echo Killing process on port 8000: %%a
    taskkill /f /pid %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001') do (
    echo Killing process on port 3001: %%a
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo ✅ All trading platform processes terminated
echo Ports 8000 and 3001 are now free
echo.
echo You can now run start_trading_platform.bat for a fresh start
echo.
pause