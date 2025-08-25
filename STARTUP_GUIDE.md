# Trading Platform - Step-by-Step Startup Guide

## Quick Diagnosis

If `start.bat` failed, run this first to see what's wrong:

```batch
debug.bat
```

This will check all prerequisites and show you exactly what's missing.

## Prerequisites Check

### 1. Install Python (if missing)
- Download from: https://python.org/downloads/
- **IMPORTANT**: Check "Add Python to PATH" during installation
- Verify: Open cmd and run `python --version`

### 2. Install Node.js (if missing)
- Download from: https://nodejs.org/
- Install the LTS version
- Verify: Open cmd and run `node --version` and `npm --version`

## Manual Step-by-Step Startup

If the automated scripts fail, follow these steps manually:

### Step 1: Create Virtual Environment
```batch
python -m venv venv
```
**If this fails**: Python is not installed or not in PATH

### Step 2: Activate Virtual Environment
```batch
venv\Scripts\activate.bat
```
**If this fails**: Virtual environment creation failed

### Step 3: Install Python Dependencies
```batch
pip install -r requirements.txt
```
**If this fails**: 
- Internet connection issue
- Missing C++ build tools
- Try: `python -m pip install --upgrade pip` first

### Step 4: Install Frontend Dependencies
```batch
cd frontend
npm install
cd ..
```
**If this fails**:
- Node.js not installed
- Internet connection issue
- Try: `npm cache clean --force`

### Step 5: Create Configuration
```batch
echo DATABASE_URL=sqlite:///./trading_platform.db > .env
echo API_HOST=localhost >> .env
echo API_PORT=8000 >> .env
echo LOG_LEVEL=INFO >> .env
```

### Step 6: Initialize Database
```batch
python -c "from trading_platform.database.database import init_database; init_database()"
```
**If this fails**: Package import issue or database permissions

### Step 7: Test Backend
```batch
python -c "from trading_platform.api.main import app; print('API loaded')"
```
**If this fails**: Check import errors

### Step 8: Start Backend (Terminal 1)
```batch
venv\Scripts\activate
python -m uvicorn trading_platform.api.main:app --reload --host localhost --port 8000
```

### Step 9: Start Frontend (Terminal 2)
```batch
cd frontend
npm start
```

## Common Error Solutions

### Error: "Python is not recognized"
**Solution**: 
1. Install Python from python.org
2. During installation, check "Add Python to PATH"
3. Restart command prompt

### Error: "Node is not recognized"
**Solution**:
1. Install Node.js from nodejs.org
2. Restart command prompt

### Error: "pip install failed"
**Solutions**:
1. Update pip: `python -m pip install --upgrade pip`
2. Install Visual Studio Build Tools if on Windows
3. Check internet connection

### Error: "No module named 'trading_platform'"
**Solutions**:
1. Make sure you're in the correct directory
2. Activate virtual environment: `venv\Scripts\activate`
3. Reinstall requirements: `pip install -r requirements.txt`

### Error: "Port 8000 already in use"
**Solutions**:
1. Find what's using the port: `netstat -ano | findstr :8000`
2. Kill the process or restart computer
3. Use different port: `--port 8001`

### Error: "npm install failed"
**Solutions**:
1. Clear npm cache: `npm cache clean --force`
2. Delete node_modules: `rmdir /s frontend\node_modules`
3. Try again: `cd frontend && npm install`

### Error: Database/Import Issues
**Solutions**:
1. Check file permissions
2. Run as administrator
3. Check antivirus settings

## Simplified Startup (No Monitoring)

If the full startup is too complex, use this minimal version:

### Terminal 1 - Backend Only:
```batch
venv\Scripts\activate
python -m uvicorn trading_platform.api.main:app --reload
```

### Terminal 2 - Frontend Only:
```batch
cd frontend
npm start
```

Then access:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Getting Help

1. **Run debug script**: `debug.bat`
2. **Check log file**: `trading_platform.log`
3. **Check specific error windows** that open
4. **Take screenshot** of any error messages

## Alternative: Docker Setup

If all else fails, try Docker:

```batch
# Install Docker Desktop first
docker-compose up --build
```

This bypasses all local dependency issues.

## Manual Testing

To test if everything works without the full startup:

```batch
# Test Python imports
venv\Scripts\activate
python -c "import fastapi, pandas; print('Working!')"

# Test API loading
python -c "from trading_platform.api.main import app; print('API OK')"

# Test database
python -c "from trading_platform.database.database import init_database; init_database(); print('DB OK')"
```

If any of these fail, that's where the problem is.