@echo off
setlocal
title Stop - Trading Platform
cd /d "%~dp0.."

echo ========================================
echo   Stopping Trading Platform
echo ========================================
echo.
echo Freeing ports 8000 (backend) and 3001 (frontend)...
echo.

REM Kill by port only - safer than killing all python.exe / node.exe
set killed=0

for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    echo   Stopping backend  (PID %%a)...
    taskkill /f /pid %%a >nul 2>&1
    set killed=1
)

for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3001 "') do (
    echo   Stopping frontend (PID %%a)...
    taskkill /f /pid %%a >nul 2>&1
    set killed=1
)

if "%killed%"=="0" (
    echo   Nothing was running on ports 8000 / 3001.
)

echo.
echo Done. Ports 8000 and 3001 are now free.
echo Run START.bat to launch the platform again.
echo.
pause