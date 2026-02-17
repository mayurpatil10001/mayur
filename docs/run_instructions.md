# Running the Trading Optimization Platform

## Prerequisites

- **Python 3.11+** with `pip` (verify: `python --version`)
- **Node.js 18+** with `npm` (verify: `node --version`)

## Quick Start (Automated)

Double-click `start_trading_platform.bat` in the project root.
This will kill old processes, start the backend and frontend in separate windows.

## Manual Start

### 1. Activate virtual environment

```powershell
cd "c:\SierraChart\SC results WF"
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies (first time only)

```powershell
pip install -r requirements.txt
cd frontend; npm install; cd ..
```

### 3. Start Backend (Terminal 1)

```powershell
cd "c:\SierraChart\SC results WF"
.\venv\Scripts\Activate.ps1
python -m uvicorn trading_platform.api.main:app --host localhost --port 8000 --reload
```

Backend is ready when you see `Uvicorn running on http://localhost:8000`.

### 4. Start Frontend (Terminal 2)

```powershell
cd "c:\SierraChart\SC results WF\frontend"
npm start
```

Frontend is ready when you see `Compiled successfully!` and opens at http://localhost:3001.

## URLs

| Service | URL |
|---------|-----|
| Frontend Dashboard | http://localhost:3001 |
| Backend API | http://localhost:8000 |
| Swagger API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

## Running Tests

```powershell
cd "c:\SierraChart\SC results WF"
.\venv\Scripts\Activate.ps1

# Go/No-Go tests (Phase 1 + 2)
python -m pytest tests/test_trade_import_go_no_go.py -v --tb=short
python -m pytest tests/test_account_management_go_no_go.py -v --tb=short

# All tests
python -m pytest tests/ -v --tb=short
```

## Trade Import (Copy-Paste)

1. Open Sierra Chart → Trade Activity Log → Select All → Copy
2. Navigate to http://localhost:8000/docs
3. Expand `POST /api/v1/trades/import-preview`
4. Paste the copied text into the `text` field
5. Click **Execute** to preview
6. If preview looks correct, use `POST /api/v1/trades/import-paste` to import

## Stopping the Platform

```powershell
# Or double-click kill_trading_platform.bat
taskkill /f /im python.exe
taskkill /f /im node.exe
```

## Docker (Alternative)

```powershell
docker-compose up --build
```
