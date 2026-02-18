@echo off
echo ========================================
echo  TRADING PLATFORM LOG MONITOR
echo ========================================
echo.
echo Monitoring logs in real-time...
echo Press Ctrl+C to stop monitoring
echo.

:loop
echo [%time%] Checking logs...
if exist trading_platform.log (
    echo --- BACKEND LOGS (Last 10 lines) ---
    powershell "Get-Content trading_platform.log -Tail 10"
    echo.
)

echo --- CHECKING API HEALTH ---
curl -s http://localhost:8000/health 2>nul || echo API not responding

echo --- CHECKING ACCOUNTS DEBUG ---
curl -s http://localhost:8000/api/accounts/debug 2>nul || echo Accounts debug not responding

echo.
echo ========================================
timeout /t 10 /nobreak > nul
goto loop