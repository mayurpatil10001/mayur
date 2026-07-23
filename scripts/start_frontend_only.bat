@echo off
setlocal
title Frontend - Trading Dashboard
cd /d "%~dp0.."

echo ========================================
echo   Trading Platform  -  Frontend Only
echo ========================================
echo.

REM Kill anything on port 3001
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3001 "') do taskkill /f /pid %%a >nul 2>&1
echo [1/2] Port 3001 cleared.

echo.
echo [2/2] Starting frontend on http://localhost:3001 ...
echo       Make sure backend is running on http://localhost:8000
echo.

cd frontend
npm start