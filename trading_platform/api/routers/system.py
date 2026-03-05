from fastapi import APIRouter, Depends, HTTPException, Query, Body, BackgroundTasks
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
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import sqlite3

NY_TZ = ZoneInfo("America/New_York")

router = APIRouter(prefix="/api/system", tags=["system"])

@router.post("/audit-trades")
async def audit_trades(
    account: str = Body(...),
    date: str = Body(...),
    raw_text: str = Body(...)
):
    """
    Compares DB trades with copy-pasted SC data.
    """
    db_path = "trading_platform.db"
    
    # 1. Fetch from DB (Capture wider range to handle TZ shifts, then filter in Python)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Fetch +/- 1 day to be absolutely sure we catch any TZ edge cases
    c.execute("""
        SELECT side, quantity as qty, entry_price, exit_price, profit_loss as pnl, entry_time, exit_time
        FROM processed_trades
        WHERE account_name = ? COLLATE NOCASE 
          AND entry_time >= date(?, '-1 day') 
          AND entry_time <= date(?, '+2 days')
        ORDER BY entry_time ASC
    """, (account, date, date))
    
    # Filter by converted NY date in Python for precision
    db_trades = []
    for r in c.fetchall():
        try:
            dt_utc = datetime.fromisoformat(r['entry_time'].replace('Z', ''))
            # Some entries might not have Z but are UTC
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            ny_date = dt_utc.astimezone(NY_TZ).date().isoformat()
            if ny_date == date:
                db_trades.append(dict(r))
        except: continue
    conn.close()

    # 2. Parse Raw Text (SC Tab-separated)
    lines = raw_text.strip().split('\n')
    if not lines:
        return {"error": "Empty data"}

    header = lines[0].split('\t')
    def find_idx(keywords):
        for i, h in enumerate(header):
            if any(k.lower() in h.lower() for k in keywords): return i
        return -1

    cols = {
        'side': find_idx(['side', 'buy/sell']),
        'qty': find_idx(['quantity', 'trade quant', 'quant']),
        'entry_dt': find_idx(['entry date time', 'entrydatetime']),
        'exit_dt': find_idx(['exit date time', 'exitdatetime']),
        'entry_px': find_idx(['entry price', 'entryprice']),
        'exit_px': find_idx(['exit price', 'exitprice']),
        'pnl': find_idx(['profit/loss', 'p/l', 'profit']),
    }

    sc_trades = []
    start_row = 1 if any(k in lines[0].lower() for k in ['side', 'entry', 'price']) else 0
    for line in lines[start_row:]:
        parts = line.split('\t')
        if len(parts) < 5: continue
        try:
            raw_side = parts[cols['side']].upper() if cols['side'] != -1 else "LONG"
            side = "LONG" if "BUY" in raw_side or "LONG" in raw_side else "SHORT"
            qty = int(float(parts[cols['qty']].replace(',', ''))) if cols['qty'] != -1 else 1
            en_px = float(parts[cols['entry_px']].replace(',', '')) if cols['entry_px'] != -1 else 0
            ex_px = float(parts[cols['exit_px']].replace(',', '')) if cols['exit_px'] != -1 else 0
            pnl = float(parts[cols['pnl']].replace('$', '').replace(',', '')) if cols['pnl'] != -1 else 0.0
            en_dt = parts[cols['entry_dt']] if cols['entry_dt'] != -1 else ""
            ex_dt = parts[cols['exit_dt']] if cols['exit_dt'] != -1 else ""
            
            sc_trades.append({
                'side': side, 'qty': qty, 'entry_price': en_px, 'exit_price': ex_px,
                'pnl': pnl, 'entry_time': en_dt, 'exit_time': ex_dt
            })
        except: continue

    # 3. Match: entry+exit both on time and price (within tolerance) = match
    matched_count = 0
    db_only = []
    sc_only = sc_trades.copy()
    entry_exit_sec = 90  # allow 90s for entry/exit time match (TZ and rounding)
    price_tol = 2.0     # $2 for entry/exit price

    for dt in db_trades:
        try:
            en_utc = datetime.fromisoformat(dt['entry_time'].replace('Z', ''))
            if en_utc.tzinfo is None:
                en_utc = en_utc.replace(tzinfo=timezone.utc)
            ex_utc = datetime.fromisoformat(dt['exit_time'].replace('Z', ''))
            if ex_utc.tzinfo is None:
                ex_utc = ex_utc.replace(tzinfo=timezone.utc)
            ny_en = en_utc.astimezone(NY_TZ).replace(tzinfo=None)
            ny_ex = ex_utc.astimezone(NY_TZ).replace(tzinfo=None)

            found_idx_sc = -1
            best_err = float('inf')
            for i, st in enumerate(sc_only):
                try:
                    st_en = datetime.fromisoformat(st['entry_time'].replace(' ', 'T'))
                    st_ex = (datetime.fromisoformat(st['exit_time'].replace(' ', 'T'))
                             if (st.get('exit_time') and str(st['exit_time']).strip()) else st_en)
                    if st['side'] != dt['side']:
                        continue
                    entry_diff = abs((ny_en - st_en).total_seconds())
                    exit_diff = abs((ny_ex - st_ex).total_seconds())
                    if entry_diff > entry_exit_sec or exit_diff > entry_exit_sec:
                        continue
                    if abs(st['entry_price'] - dt['entry_price']) > price_tol or abs(st['exit_price'] - dt['exit_price']) > price_tol:
                        continue
                    err = entry_diff + exit_diff
                    if err < best_err:
                        best_err = err
                        found_idx_sc = i
                except Exception:
                    continue

            if found_idx_sc != -1:
                sc_only.pop(found_idx_sc)
                matched_count += 1
            else:
                db_only.append(dt)
        except Exception:
            db_only.append(dt)

    return {
        "summary": {
            "db_count": len(db_trades),
            "sc_count": len(sc_trades),
            "matched": matched_count,
            "db_pnl": sum(t['pnl'] for t in db_trades),
            "sc_pnl": sum(t['pnl'] for t in sc_trades),
            "db_qty": sum(t['qty'] for t in db_trades),
            "sc_qty": sum(t['qty'] for t in sc_trades)
        },
        "discrepancies": {
            "db_only": db_only[:20], # Sample
            "sc_only": sc_only[:20]  # Sample
        }
    }


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
        # Use a faster check instead of full COUNT(*)
        result = db.execute(text("SELECT 1 FROM processed_trades LIMIT 1"))
        has_trades = result.scalar() is not None
        response_time = int((time.time() - start_time) * 1000)
        
        status_list.append({
            "component": "Trades Table",
            "status": "online" if has_trades else "warning",
            "lastUpdate": "just now",
            "responseTime": response_time,
            "note": "Table accessible"
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
        # Use a faster check for accounts
        result = db.execute(text("SELECT account_name FROM processed_trades LIMIT 1"))
        has_accounts = result.scalar() is not None
        response_time = int((time.time() - start_time) * 1000)
        
        status_list.append({
            "component": "Accounts",
            "status": "online" if has_accounts else "warning",
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
        # Trigger reload by touching main.py
        # We look for main.py relative to the current working directory or via package structure
        paths_to_try = [
            Path("trading_platform/api/main.py"),
            Path(__file__).parent.parent / "main.py",
            Path("api/main.py")
        ]
        
        main_py = None
        for p in paths_to_try:
            if p.exists():
                main_py = p
                break
                
        if main_py:
            # Update mtime. On Windows, sometimes appending a space/newline is more reliable for dev-watchers
            # than just utime if the watcher is using content-hashes instead of mtime.
            # But here we stick to utime but with an explicit open/close to be sure.
            with open(main_py, 'a') as f:
                os.utime(main_py, None)
            return {"status": "restarting", "message": "Backend restart triggered. Service will reload in a few seconds."}
        else:
            raise HTTPException(status_code=500, detail="Could not locate main.py to trigger reload")
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
            cursor.execute("DELETE FROM pending_fills WHERE account_name = ? AND symbol = ?", (account, symbol))
        else:
            cursor.execute("DELETE FROM processed_trades WHERE account_name = ?", (account,))
            cursor.execute("DELETE FROM pending_fills WHERE account_name = ?", (account,))
        
        deleted = cursor.rowcount
        conn.commit()
        return {"status": "success", "message": f"Deleted {deleted} trades and cleared pending state", "count": deleted}
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
        "progress": importer.progress,
        "finish_time": getattr(importer, 'finish_time', None)
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

@router.post("/import-start")
async def start_import(background_tasks: BackgroundTasks, request: dict = Body(...)):
    from trading_platform.services.binary_log_parser import importer
    if importer.running:
        return {"message": "Import already running", "running": True}
        
    paths = request.get("paths", [])
    symbol = request.get("symbol", None)
    accounts = request.get("accounts", None) 
    
    from trading_platform.services.settings import settings_service
    settings = settings_service.get_settings()
    try:
        days = int(request.get("days", settings.get("import_days", 2000)))
    except:
        days = 2000
    
    if not paths:
        return {"message": "No paths provided", "running": False}
        
    background_tasks.add_task(importer.run_import, paths, symbol, accounts, days_lookback=days)
    return {"message": f"Import started{' for ' + str(accounts) if accounts else ''} (Last {days} days)", "running": True}

@router.post("/import-stop")
async def stop_import():
    from trading_platform.services.binary_log_parser import importer
    importer.stop()
    return {"message": "Stopping import...", "running": False}

@router.post("/check-path")
async def check_path(request: dict = Body(...)):
    try:
        import glob
        import os
        import re
        import datetime
        from trading_platform.services.settings import settings_service

        path = request.get("path", "")
        target_symbol = request.get("symbol", "").upper()
        settings = settings_service.get_settings()
        try:
            days_limit = int(settings.get("import_days", 2000))
        except:
            days_limit = 2000
            
        cutoff_time = (datetime.datetime.now() - datetime.timedelta(days=days_limit)).timestamp() if days_limit > 0 else 0
        
        if not path:
            return {"exists": False, "files": [], "message": "No path provided"}
            
        clean_path = os.path.normpath(path)
        if not os.path.exists(clean_path):
            return {"exists": False, "files": [], "message": f"Path not found: {clean_path}"}
            
        all_files_raw = glob.glob(os.path.join(clean_path, "*.txt")) + \
                        glob.glob(os.path.join(clean_path, "*.log")) + \
                        glob.glob(os.path.join(clean_path, "*.data"))
        
        all_files = [f for f in all_files_raw if os.path.getmtime(f) >= cutoff_time]
        
        if not all_files:
            return {"exists": True, "files": [], "count": 0, "accounts": [], "message": "No recent files found"}

        account_files = {}
        for f in all_files:
            try:
                fname = os.path.basename(f)
                parts = fname.split('.')
                if len(parts) > 1:
                    account = parts[-2].upper()
                    account = re.sub(r'_UTC$', '', account)
                    if account not in account_files:
                        account_files[account] = []
                    account_files[account].append(f)
            except: pass

        detected_accounts = []
        for account, files in account_files.items():
            if not target_symbol:
                detected_accounts.append(account)
                continue
                
            # Priority 1: Smart Match (Symbol in filename or start of account name)
            if any(target_symbol in os.path.basename(f).upper() for f in files) or account.upper().startswith(target_symbol):
                detected_accounts.append(account)
            # Priority 2: NQ Catch-all (Exclude obvious ES/CL/FDAX prefixes)
            elif target_symbol == "NQ" and not any(account.upper().startswith(s) for s in ["ES-", "ES_", "CL-", "CL_", "FDAX-", "FDAX_"]):
                detected_accounts.append(account)

        # Final Fallback: If we found files but NO accounts matched the symbol filter,
        # show ALL accounts so the user can see what's in the folder and choose manually.
        if target_symbol and not detected_accounts and all_files:
            detected_accounts = sorted(list(account_files.keys()))

        return {
            "exists": True, 
            "count": len(all_files),
            "accounts": detected_accounts,
            "message": f"Found {len(all_files)} files."
        }
        
    except Exception as e:
        return {"exists": False, "files": [], "message": f"Scan Failed: {str(e)}"}

@router.post("/purge-anomalies")
async def purge_anomalies_endpoint(request: dict = Body(...)):
    from trading_platform.services.binary_log_parser import importer
    account = request.get("account")
    symbol = request.get("symbol")
    if not account:
        raise HTTPException(status_code=400, detail="Account required")
    
    res = importer.purge_anomalies(account, symbol, purge_overnight=True)
    return {"message": "Data cleaned successfully", "removed": res}

@router.post("/wipe-db")
async def wipe_database():
    """Wipes all trade data from the database."""
    import sqlite3
    db_path = Path("trading_platform.db")
    if not db_path.exists():
        return {"status": "success", "message": "Database file not found, nothing to wipe"}
        
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        tables_to_wipe = [
            'processed_trades', 'pending_fills', 'position_state', 
            'temporal_performance', 'performance_metrics', 'trades',
            'walk_forward_results', 'monte_carlo_results', 'data_import_log'
        ]
        total_deleted = 0
        for table in tables_to_wipe:
            try:
                cursor.execute(f"DELETE FROM {table}")
                total_deleted += cursor.rowcount
            except: pass # Table might not exist or be empty
            
        conn.commit()
        # VACUUM must be run outside of a transaction
        conn.isolation_level = None
        conn.execute("VACUUM")
        
        return {"status": "success", "message": "Database wiped successfully.", "deleted_count": total_deleted}
    except Exception as e:
        try: conn.rollback()
        except: pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
