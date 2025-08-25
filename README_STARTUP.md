# Trading Platform Startup Guide

## Quick Start (Recommended)

### Option 1: Start Everything
```bash
start_trading_platform.bat
```
This will:
- ✅ Activate the Python virtual environment
- ✅ Start the backend API on http://localhost:8000
- ✅ Start the React frontend on http://localhost:3001
- ✅ Open both in separate command windows

### Option 2: Start Components Separately

#### Backend Only
```bash
start_backend_only.bat
```
- Starts API server on http://localhost:8000
- API docs available at http://localhost:8000/docs

#### Frontend Only
```bash
start_frontend_only.bat
```
- Starts React app on http://localhost:3001
- Requires backend to be running first

## Alternative: Simple HTML Dashboard

If the React frontend has issues, use the simple HTML dashboard:

1. Make sure backend is running (`start_backend_only.bat`)
2. Open `working_dashboard.html` in your browser
3. This bypasses React and connects directly to the API

## URLs After Startup

| Service | URL | Description |
|---------|-----|-------------|
| Backend API | http://localhost:8000 | Main API server |
| API Documentation | http://localhost:8000/docs | Interactive API docs |
| Health Check | http://localhost:8000/health | Server status |
| React Frontend | http://localhost:3001 | Main web interface |
| Simple Dashboard | working_dashboard.html | Backup HTML interface |

## Troubleshooting

### Backend Won't Start
- Check if virtual environment exists: `venv\Scripts\activate.bat`
- Install missing dependencies: `pip install -r requirements.txt`
- Check if port 8000 is already in use: `netstat -an | findstr :8000`

### Frontend Won't Start
- Make sure you're in the frontend directory: `cd frontend`
- Install dependencies: `npm install`
- Check if port 3001 is available: `netstat -an | findstr :3001`

### CORS Errors
- Make sure backend started successfully
- Check backend logs for errors
- Try the simple HTML dashboard instead

### No Accounts Loading
- Verify database exists: `trading_platform.db`
- Check backend health: http://localhost:8000/health
- Try API directly: http://localhost:8000/api/v1/accounts/?size=5

## Database Info

Your trading data is stored in `trading_platform.db` with:
- **675,743 total trades**
- **44 unique accounts**
- Multiple symbols (CL, NQ, FDAX, etc.)

## Development Notes

- Backend runs with auto-reload (changes restart server)
- Frontend runs with hot-reload (changes update browser)
- Both services log to their respective command windows
- Use Ctrl+C to stop either service

## Need Help?

1. Check the command windows for error messages
2. Try the simple HTML dashboard first
3. Verify backend health endpoint
4. Check if all dependencies are installed