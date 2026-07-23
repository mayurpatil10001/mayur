@echo off
setlocal EnableDelayedExpansion
title Trading Optimization Platform

REM ─────────────────────────────────────────────────────────────────
REM  START.bat  –  One-click launcher for the Trading Platform
REM  Starts: Backend (port 8000) + Frontend (port 3001)
REM  Then auto-opens the dashboard in your default browser.
REM ─────────────────────────────────────────────────────────────────

cd /d "%~dp0"

echo.
echo  ████████╗██████╗  █████╗ ██████╗ ███████╗
echo  ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝
echo     ██║   ██████╔╝███████║██║  ██║█████╗
echo     ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝
echo     ██║   ██║  ██║██║  ██║██████╔╝███████╗
echo     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝
echo.
echo  Trading Optimization Platform  ^|  High Sortino Edition
echo  ════════════════════════════════════════════════════════
echo.

REM ── Step 1: Kill any leftover processes on ports 8000 / 3001 ──────
echo  [1/4] Cleaning up old processes...

for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3001 "') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo  ✓ Ports cleared.
echo.

REM ── Step 2: Verify Python ─────────────────────────────────────────
echo  [2/4] Checking Python...

set PYTHON_EXE=C:\Users\hp\AppData\Local\Programs\Python\Python311\python.exe

if not exist "%PYTHON_EXE%" (
    REM Fallback: try python on PATH
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo  ✗ ERROR: Python not found.
        echo    Expected: %PYTHON_EXE%
        echo    Install Python 3.11 from https://python.org
        pause
        exit /b 1
    )
    set PYTHON_EXE=python
)

"%PYTHON_EXE%" --version 2>&1 | findstr /i "python" >nul
if %errorlevel% neq 0 (
    echo  ✗ ERROR: Python check failed.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('"%PYTHON_EXE%" --version 2^>^&1') do echo  ✓ Found %%v

REM ── Step 3: Check Node / npm ──────────────────────────────────────
echo.
echo  [3/4] Checking Node.js...

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo  ✗ ERROR: npm not found. Install Node.js from https://nodejs.org
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('npm --version 2^>^&1') do echo  ✓ npm v%%v

REM ── Step 4: Launch Backend in new window ─────────────────────────
echo.
echo  [4/4] Launching services...
echo.

if not exist "main.py" (
    echo  ✗ ERROR: main.py not found in %cd%
    echo    Make sure you are running START.bat from the project root.
    pause
    exit /b 1
)

if not exist "trading_platform.db" (
    echo  ⚠  WARNING: trading_platform.db not found.
    echo     Data may not be available until import is run.
    echo.
)

echo  Starting Backend  ^(http://localhost:8000^)...
start "Backend – Trading Platform" cmd /k "title Backend - Trading Platform && cd /d "%~dp0" && "%PYTHON_EXE%" main.py"

echo  Waiting 6s for backend to initialize...
timeout /t 6 /nobreak >nul

REM ── Step 5: Launch Frontend in new window ────────────────────────
echo  Starting Frontend ^(http://localhost:3001^)...
start "Frontend – Trading Dashboard" cmd /k "title Frontend - Trading Dashboard && cd /d "%~dp0frontend" && npm start"

echo  Waiting 12s for frontend to compile...
timeout /t 12 /nobreak >nul

REM ── Step 6: Open browser ─────────────────────────────────────────
echo  Opening dashboard in browser...
start "" "http://localhost:3001"

REM ── Done ─────────────────────────────────────────────────────────
echo.
echo  ════════════════════════════════════════════════════════
echo   🚀  SYSTEM IS STARTING UP
echo  ════════════════════════════════════════════════════════
echo.
echo   Backend API   ▶  http://localhost:8000
echo   API Docs      ▶  http://localhost:8000/docs
echo   Dashboard     ▶  http://localhost:3001
echo.
echo   Two new windows have opened:
echo     • "Backend  – Trading Platform"
echo     • "Frontend – Trading Dashboard"
echo.
echo   Watch the Frontend window for "Compiled successfully!"
echo   then refresh the browser if needed.
echo.
echo   To stop: close those two windows, or run:
echo     scripts\kill_trading_platform.bat
echo.
echo  ════════════════════════════════════════════════════════
echo.
pause >nul
