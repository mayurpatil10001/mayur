@echo off
setlocal
title Backend – Trading Platform
cd /d "%~dp0.."

echo ========================================
echo   Trading Platform  –  Backend Only
echo ========================================
echo.

REM Kill anything on port 8000
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do taskkill /f /pid %%a >nul 2>&1
echo [1/2] Port 8000 cleared.

if not exist "trading_platform.db" echo WARNING: trading_platform.db not found.

echo.
echo [2/2] Starting backend on http://localhost:8000 ...
echo       API Docs: http://localhost:8000/docs
echo.

set PYTHON_EXE=python

"%PYTHON_EXE%" main.py