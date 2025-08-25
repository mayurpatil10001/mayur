@echo off
echo ========================================
echo   Trading Platform Frontend Only
echo ========================================
echo.

REM Kill existing frontend processes
echo [1/2] Cleaning up existing frontend processes...
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im npm.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001') do taskkill /f /pid %%a >nul 2>&1
echo ✅ Frontend cleanup complete

timeout /t 1 /nobreak >nul

echo.
echo [2/2] Starting React frontend...
echo Frontend will run on: http://localhost:3001
echo.
echo Make sure the backend is running on http://localhost:8000
echo.

cd frontend
npm start
cd ..