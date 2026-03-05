import sqlite3
import re
import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict

NY_TZ = ZoneInfo("America/New_York")

def parse_sc_pasted_data(text: str) -> List[Dict]:
    """
    Parses copy-pasted data from Sierra Chart 'Trades' or 'Trade Activity' tab.
    Handles tab-separated values.
    """
    lines = text.strip().split('\n')
    if not lines:
        return []

    # Detect header or assume standard columns
    # We look for keywords to identify column indices
    header = lines[0].split('\t')
    
    # Common SC column headers
    cols = {
        'side': -1, 'qty': -1, 'entry_dt': -1, 'exit_dt': -1, 
        'entry_px': -1, 'exit_px': -1, 'pnl': -1, 'account': -1
    }
    
    def find_idx(keywords):
        for i, h in enumerate(header):
            if any(k.lower() in h.lower() for k in keywords):
                return i
        return -1

    cols['side'] = find_idx(['side', 'buy/sell'])
    cols['qty'] = find_idx(['quantity', 'trade quant', 'quant'])
    cols['entry_dt'] = find_idx(['entry date time', 'entrydatetime'])
    cols['exit_dt'] = find_idx(['exit date time', 'exitdatetime'])
    cols['entry_px'] = find_idx(['entry price', 'entryprice'])
    cols['exit_px'] = find_idx(['exit price', 'exitprice'])
    cols['pnl'] = find_idx(['profit/loss', 'p/l', 'profit'])
    cols['account'] = find_idx(['account'])

    # If header not found or missing critical columns, try positional defaults
    # (Sometimes users don't copy the header)
    is_header = any(k in lines[0].lower() for k in ['side', 'entry', 'price', 'trade'])
    start_row = 1 if is_header else 0
    
    sc_trades = []
    for line in lines[start_row:]:
        parts = line.split('\t')
        if len(parts) < 5: continue
        
        try:
            # Side
            raw_side = parts[cols['side']].upper() if cols['side'] != -1 else parts[3]
            side = "LONG" if "BUY" in raw_side or "LONG" in raw_side else "SHORT"
            
            # Qty
            qty = int(float(parts[cols['qty']].replace(',', ''))) if cols['qty'] != -1 else int(parts[4])
            
            # Prices
            en_px = float(parts[cols['entry_px']].replace(',', '')) if cols['entry_px'] != -1 else float(parts[7])
            ex_px = float(parts[cols['exit_px']].replace(',', '')) if cols['exit_px'] != -1 else float(parts[8])
            
            # PnL
            pnl = float(parts[cols['pnl']].replace('$', '').replace(',', '')) if cols['pnl'] != -1 else 0.0
            
            # Times (Expects YYYY-MM-DD HH:MM:SS)
            en_dt_str = parts[cols['entry_dt']] if cols['entry_dt'] != -1 else parts[5]
            ex_dt_str = parts[cols['exit_dt']] if cols['exit_dt'] != -1 else parts[6]
            
            # SC exports usually have fractional seconds or just seconds
            def clean_dt(s):
                s = s.strip()
                # Handle 2025-12-18 04:05:56.123 -> ISO
                return s.replace(' ', 'T')

            sc_trades.append({
                'side': side,
                'qty': qty,
                'entry_price': en_px,
                'exit_price': ex_px,
                'pnl': pnl,
                'entry_time': clean_dt(en_dt_str),
                'exit_time': clean_dt(ex_dt_str)
            })
        except Exception as e:
            # print(f"Skip line due to error: {e}")
            continue
            
    return sc_trades

def fetch_db_trades(db_path: str, account: str, date_str: str) -> List[Dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Query for the specific day (using NY time conversion for query if needed, 
    # but here we just look at entry_time date)
    c.execute("""
        SELECT side, quantity, entry_price, exit_price, profit_loss, entry_time, exit_time
        FROM processed_trades
        WHERE account_name = ? COLLATE NOCASE AND date(entry_time) = ?
        ORDER BY entry_time ASC
    """, (account, date_str))
    
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def compare_trades(db_trades: List[Dict], sc_trades: List[Dict]):
    print(f"\n--- AUDIT REPORT ---")
    print(f"DB Trades Found: {len(db_trades)}")
    print(f"SC Trades Found: {len(sc_trades)}")
    
    db_pnl = sum(t['profit_loss'] for t in db_trades)
    sc_pnl = sum(t['pnl'] for t in sc_trades)
    
    db_qty = sum(t['quantity'] for t in db_trades)
    sc_qty = sum(t['qty'] for t in sc_trades)
    
    print(f"\nSummary Comparison:")
    print(f"{'Metric':<15} | {'Database':<15} | {'Sierra Chart':<15} | {'Diff':<15}")
    print("-" * 65)
    print(f"{'Total PnL':<15} | ${db_pnl:>13.2f} | ${sc_pnl:>13.2f} | ${db_pnl - sc_pnl:>13.2f}")
    print(f"{'Contracts':<15} | {db_qty:>14} | {sc_qty:>14} | {db_qty - sc_qty:>14}")

    print(f"\nDetailed Trade-by-Trade matching (Experimental):")
    # Time-based matching
    # Convert DB times (UTC) to NY for comparison with SC (usually NY)
    matched = 0
    mismatched = []
    
    temp_sc = sc_trades.copy()
    
    for dt in db_trades:
        # Convert DB entry_time to naive NY comparison
        try:
            # DB: 2025-12-18T09:05:56.979054 (UTC)
            dt_utc = datetime.datetime.fromisoformat(dt['entry_time'])
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
            ny_dt = dt_utc.astimezone(NY_TZ).replace(tzinfo=None)
            
            # Find closest match in SC by entry time and side
            found = None
            best_diff = 30 # 30 second window
            
            for i, st in enumerate(temp_sc):
                try:
                    st_en = datetime.datetime.fromisoformat(st['entry_time'])
                    time_diff = abs((ny_dt - st_en).total_seconds())
                    
                    if time_diff < best_diff and st['side'] == dt['side']:
                        # Also check price roughly
                        if abs(st['entry_price'] - dt['entry_price']) < 1.0:
                            found = i
                            best_diff = time_diff
                except: continue
            
            if found is not None:
                st = temp_sc.pop(found)
                matched += 1
            else:
                mismatched.append(dt)
        except Exception as e:
            print(f"Error matching DB trade: {e}")

    print(f"Perfect Matches: {matched}")
    print(f"Missing in SC (Database-only): {len(mismatched)}")
    print(f"Missing in Database (SC-only): {len(temp_sc)}")
    
    if mismatched:
        print(f"\nSample Data-only trades (Discrepancies):")
        for m in mismatched[:5]:
            print(f" - {m['entry_time']} | {m['side']} | Qty: {m['quantity']} | Px: {m['entry_price']} | PnL: {m['profit_loss']}")

    if temp_sc:
        print(f"\nSample SC-only trades (Ghosted in SC but rejected by Importer?):")
        for s in temp_sc[:5]:
            print(f" - {s['entry_time']} | {s['side']} | Qty: {s['qty']} | Px: {s['entry_price']} | PnL: {s['pnl']}")

def run_cli_audit():
    import sys
    print("--- TRADING PLATFORM AUDIT TOOL ---")
    db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
    
    account = input("Enter Account Name (e.g. V_SIM16): ").strip()
    date_str = input("Enter Date (YYYY-MM-DD): ").strip()
    
    db_trades = fetch_db_trades(db_path, account, date_str)
    if not db_trades:
        print(f"No trades found in database for {account} on {date_str}.")
        return

    print(f"Database contains {len(db_trades)} trades for this day.")
    print("\nPlease PASTE the Sierra Chart 'Trades' tab data here (Ctrl+V).")
    print("Press Ctrl+Z (Windows) or Ctrl+D (Unix) and Enter to finish:")
    
    try:
        pasted_text = sys.stdin.read()
    except EOFError:
        pasted_text = ""
        
    if not pasted_text.strip():
        print("No SC data provided.")
        return
        
    sc_trades = parse_sc_pasted_data(pasted_text)
    if not sc_trades:
        print("Failed to parse SC data. Make sure it's tab-separated.")
        return
        
    compare_trades(db_trades, sc_trades)

if __name__ == "__main__":
    run_cli_audit()
