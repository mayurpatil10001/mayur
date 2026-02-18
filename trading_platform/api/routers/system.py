from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import os
from pathlib import Path

from ..dependencies import get_database_session
from ...services.settings import settings_service
from ...services.market_data_service import market_data_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def get_system_status(db: Session = Depends(get_database_session)) -> List[Dict[str, Any]]:
    """Get system component status and health metrics."""
    
    status_list = []
    
    # Database status
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        response_time = int((time.time() - start_time) * 1000)
        
        status_list.append({
            "component": "Database",
            "status": "online" if response_time < 100 else "warning",
            "lastUpdate": "just now",
            "responseTime": response_time
        })
    except Exception as e:
        status_list.append({
            "component": "Database",
            "status": "offline",
            "lastUpdate": "error",
            "responseTime": None
        })
    
    # API Server status
    status_list.append({
        "component": "API Server",
        "status": "online",
        "lastUpdate": "just now",
        "responseTime": 5
    })
    
    # Check trades table
    try:
        start_time = time.time()
        result = db.execute(text("SELECT COUNT(*) FROM processed_trades"))
        trades_count = result.scalar()
        response_time = int((time.time() - start_time) * 1000)
        
        status_list.append({
            "component": f"Trades Table ({trades_count:,} records)",
            "status": "online" if response_time < 200 else "warning",
            "lastUpdate": "just now",
            "responseTime": response_time
        })
    except Exception:
        status_list.append({
            "component": "Trades Table",
            "status": "offline",
            "lastUpdate": "error",
            "responseTime": None
        })
    
    # Check accounts
    try:
        start_time = time.time()
        result = db.execute(text("SELECT COUNT(DISTINCT account_name) FROM processed_trades"))
        accounts_count = result.scalar()
        response_time = int((time.time() - start_time) * 1000)
        
        status_list.append({
            "component": f"Accounts ({accounts_count} active)",
            "status": "online",
            "lastUpdate": "just now",
            "responseTime": response_time
        })
    except Exception:
        pass
    
    return status_list


@router.get("/health")
async def health_check(db: Session = Depends(get_database_session)) -> Dict[str, Any]:
    """Simple health check endpoint."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "detail": str(e)
        }

@router.post("/restart")
async def restart_backend():
    """Triggers a backend restart by touching main.py"""
    try:
        # Navigate from /routers/system.py -> /api/main.py
        main_py = Path(__file__).parent.parent / "main.py"
        if main_py.exists():
            # Update mtime to trigger uvicorn reload
            os.utime(main_py, None)
            return {"status": "restarting", "message": "Backend restart triggered. Service will reload in a few seconds."}
        else:
            raise HTTPException(status_code=500, detail="Could not locate main.py")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/shutdown")
async def shutdown_server() -> Dict[str, Any]:
    """Shutdown the server (for development use only)."""
    import os
    import signal
    
    # Send shutdown signal after a short delay
    def delayed_shutdown():
        import time
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)
    
    import threading
    threading.Thread(target=delayed_shutdown).start()
    
    return {
        "status": "shutting_down",
        "message": "Server will shutdown in 1 second",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/accounts")
async def get_all_accounts(db: Session = Depends(get_database_session)) -> List[Dict[str, Any]]:
    """Get a detailed list of all accounts for the unified dashboard."""
    # We'll use a complex query to get all performance stats at once
    query = text("""
        WITH stats AS (
            SELECT 
                account_name, 
                symbol, 
                COUNT(*) as trade_count,
                COALESCE(SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END), 0) as winning_trades,
                COALESCE(SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END), 0) as losing_trades,
                COALESCE(SUM(profit_loss), 0) as total_pnl,
                COALESCE(AVG(profit_loss), 0) as avg_pnl,
                MIN(entry_time) as first_trade,
                MAX(exit_time) as last_trade
            FROM processed_trades 
            GROUP BY account_name, symbol
        ),
        timing AS (
            SELECT 
                account_name,
                base_symbol,
                day_of_week as best_day,
                hour_of_day as best_hour,
                ROW_NUMBER() OVER (PARTITION BY account_name, base_symbol ORDER BY average_profit_loss DESC) as rn
            FROM temporal_performance
        )
        SELECT 
            s.account_name as name,
            s.symbol as base_symbol,
            s.trade_count,
            s.winning_trades,
            s.losing_trades,
            s.total_pnl,
            s.avg_pnl,
            s.first_trade as first_trade_date,
            s.last_trade as last_trade_date,
            t.best_day as best_day_of_week,
            t.best_hour as best_hour_of_day
        FROM stats s
        LEFT JOIN timing t ON s.account_name = t.account_name AND s.symbol = t.base_symbol AND t.rn = 1
        ORDER BY s.account_name, s.symbol
    """)
    result = db.execute(query)
    accounts = []
    now = datetime.now()
    
    for row in result:
        acc = dict(row._mapping)
        # Calculate win rate
        tc = acc['trade_count']
        acc['win_rate'] = (acc['winning_trades'] / tc * 100) if tc > 0 else 0
        
        # Calculate days since last trade
        if acc['last_trade_date']:
            try:
                # Handle potential timezone Z or just ISO formatting
                # Handle potential timezone Z or just ISO formatting
                lt_str = acc['last_trade_date'].replace('Z', '')
                if ' ' in lt_str: lt_str = lt_str.replace(' ', 'T')
                # Use split('T')[0] for date or just parse full
                try:
                    last_dt = datetime.fromisoformat(lt_str)
                except:
                    last_dt = datetime.fromisoformat(lt_str.split('.')[0])
                
                acc['days_since_last_trade'] = (now - last_dt.replace(tzinfo=None)).days
            except:
                acc['days_since_last_trade'] = None
        else:
            acc['days_since_last_trade'] = None
            
        accounts.append(acc)
        
    return accounts

@router.post("/remove-cluster")
async def remove_cluster(
    account: str = Query(...),
    symbol: Optional[str] = Query(None)
):
    import sqlite3
    import logging
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    db_path = Path("trading_platform.db")
    
    if not db_path.exists():
        raise HTTPException(status_code=500, detail="Database file not found")
        
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        if symbol:
            cursor.execute("DELETE FROM processed_trades WHERE account_name = ? AND symbol = ?", (account, symbol))
        else:
            cursor.execute("DELETE FROM processed_trades WHERE account_name = ?", (account,))
        
        deleted = cursor.rowcount
        conn.commit()
        return {"status": "success", "message": f"Deleted {deleted} trades", "count": deleted}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/import-status")
async def get_import_status():
    from trading_platform.services.binary_log_parser import importer
    return {
        "running": importer.running,
        "message": importer.message,
        "stats": importer.stats,
        "progress": importer.progress
    }

@router.get("/settings")
async def get_settings():
    return settings_service.get_settings()

@router.post("/settings")
async def save_settings(settings: Dict[str, Any] = Body(...)):
    if settings_service.save_settings(settings):
        return {"status": "success", "message": "Settings saved"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings")

@router.post("/import-vix")
async def import_vix_data():
    """Trigger VIX historical data import."""
    try:
        count = market_data_service.fetch_vix_data(period="2y", interval="1h")
        return {"status": "success", "message": f"Successfully imported {count} VIX data points"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import VIX data: {str(e)}")

@router.get("/vix-data")
async def get_vix_data(limit: int = Query(100, ge=1, le=5000)):
    """Retrieve historical VIX data from database."""
    import sqlite3
    db_path = Path("trading_platform.db")
    if not db_path.exists():
        return {"data": []}
    
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, open_price, high_price, low_price, close_price, volume 
            FROM market_data 
            WHERE symbol = 'VIX' 
            ORDER BY date DESC 
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        data = []
        for r in rows:
            data.append({
                "timestamp": r[0],
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5]
            })
        return {"status": "success", "count": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
