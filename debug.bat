@echo off
echo ========================================
echo  Trading Platform - Debug Diagnostics
echo ========================================
echo.

:: Check current directory
echo Current directory: %CD%
echo.

:: Check Python
echo === Python Check ===
python --version 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
) else (
    echo Python location: 
    where python
)
echo.

:: Check pip
echo === Pip Check ===
pip --version 2>&1
if errorlevel 1 (
    echo ERROR: pip not found
)
echo.

:: Check Node.js
echo === Node.js Check ===
node --version 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found in PATH
) else (
    echo Node.js location:
    where node
)
echo.

:: Check npm
echo === npm Check ===
npm --version 2>&1
if errorlevel 1 (
    echo ERROR: npm not found
)
echo.

:: Check virtual environment
echo === Virtual Environment Check ===
if exist "venv\" (
    echo Virtual environment exists: YES
    if exist "venv\Scripts\activate.bat" (
        echo Activation script exists: YES
    ) else (
        echo ERROR: Activation script missing
    )
) else (
    echo Virtual environment exists: NO
)
echo.

:: Check requirements file
echo === Requirements File Check ===
if exist "requirements.txt" (
    echo requirements.txt exists: YES
    echo File size: 
    dir requirements.txt | find "requirements.txt"
) else (
    echo ERROR: requirements.txt not found
)
echo.

:: Check frontend directory
echo === Frontend Check ===
if exist "frontend\" (
    echo frontend directory exists: YES
    if exist "frontend\package.json" (
        echo package.json exists: YES
    ) else (
        echo ERROR: package.json not found
    )
) else (
    echo ERROR: frontend directory not found
)
echo.

:: Check trading_platform directory
echo === Trading Platform Package Check ===
if exist "trading_platform\" (
    echo trading_platform directory exists: YES
    if exist "trading_platform\__init__.py" (
        echo __init__.py exists: YES
    ) else (
        echo WARNING: __init__.py not found
    )
    if exist "trading_platform\api\" (
        echo api directory exists: YES
    ) else (
        echo ERROR: api directory not found
    )
) else (
    echo ERROR: trading_platform directory not found
)
echo.

:: Test Python imports if venv exists
if exist "venv\" (
    echo === Testing Python Imports ===
    call venv\Scripts\activate.bat
    
    echo Testing basic imports...
    python -c "import sys; print('Python path:', sys.executable)" 2>&1
    
    echo Testing fastapi...
    python -c "import fastapi; print('FastAPI version:', fastapi.__version__)" 2>&1
    
    echo Testing pandas...
    python -c "import pandas; print('Pandas version:', pandas.__version__)" 2>&1
    
    echo Testing numpy...
    python -c "import numpy; print('NumPy version:', numpy.__version__)" 2>&1
    
    echo Testing trading_platform...
    python -c "import trading_platform; print('Trading platform package imported successfully')" 2>&1
    
    echo Testing database module...
    python -c "from trading_platform.database.database import init_database; print('Database module imported successfully')" 2>&1
    
    echo Testing API module...
    python -c "from trading_platform.api.main import app; print('API module imported successfully')" 2>&1
)
echo.

:: Check log files
echo === Log Files Check ===
if exist "trading_platform.log" (
    echo Log file exists: YES
    echo Last 10 lines of log:
    echo ----------------------------------------
    powershell "Get-Content trading_platform.log -Tail 10"
    echo ----------------------------------------
) else (
    echo Log file exists: NO
)
echo.

:: Check ports
echo === Port Check ===
netstat -an | find "8000" > nul
if errorlevel 1 (
    echo Port 8000: FREE
) else (
    echo Port 8000: IN USE
    echo Active connections on port 8000:
    netstat -an | find "8000"
)

netstat -an | find "3000" > nul
if errorlevel 1 (
    echo Port 3000: FREE
) else (
    echo Port 3000: IN USE
    echo Active connections on port 3000:
    netstat -an | find "3000"
)
echo.

:: Check disk space
echo === Disk Space Check ===
dir | find "bytes free"
echo.

:: List all files in current directory
echo === Current Directory Contents ===
dir /b
echo.

echo ========================================
echo  Debug Complete
echo ========================================
echo.
echo If you see any errors above, those need to be fixed first.
echo Common issues and solutions:
echo.
echo 1. Python not found:
echo    - Install Python from https://python.org
echo    - Make sure to check "Add to PATH" during installation
echo.
echo 2. Node.js not found:
echo    - Install Node.js from https://nodejs.org
echo.
echo 3. Package import errors:
echo    - Run: pip install -r requirements.txt
echo.
echo 4. Ports in use:
echo    - Close other applications using ports 8000 or 3000
echo    - Or restart your computer
echo.
echo 5. Permission errors:
echo    - Run as administrator
echo    - Check antivirus settings
echo.
pause