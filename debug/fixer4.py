import os

fp = r'c:\SierraChart\SC results WF\trading_platform\services\binary_log_parser.py'
with open(fp, 'r', encoding='utf-8') as f:
    text = f.read()

target = """            # Fetch all trades to filter in Python
            
            ids_to_drop_future, ids_to_drop_long, ids_to_drop_eod = [], [], []
            pnl_future, pnl_long, pnl_eod = 0.0, 0.0, 0.0
            qty_future, qty_long, qty_eod = 0, 0, 0

            # Assuming naive ISO strings in DB are UTC
            c.execute(f"SELECT trade_id, entry_time, exit_time, profit_loss, quantity FROM processed_trades WHERE {base_where}", base_params)
            
            rows = c.fetchall()
            now_utc = datetime.datetime.now(datetime.timezone.utc) # Moved outside loop
            for tid, t1_str, t2_str, pnl, qty in rows:
                try:
                    pnl = float(pnl) if pnl else 0.0
                    qty = int(qty) if qty else 0
                    
                    t1_full = datetime.datetime.fromisoformat(t1_str)
                    t2_full = datetime.datetime.fromisoformat(t2_str)
                    
                    # Ensure timezone awareness (assume UTC if missing)
                    if t1_full.tzinfo is None: t1_full = t1_full.replace(tzinfo=datetime.timezone.utc)
                    if t2_full.tzinfo is None: t2_full = t2_full.replace(tzinfo=datetime.timezone.utc)
                    
                    reason = "KEEP"
                    
                    # 1. Future Trades
                    if t1_full > now_utc + datetime.timedelta(minutes=5):
                        reason = "FUTURE"
                        ids_to_drop_future.append(tid)
                        pnl_future += pnl
                        qty_future += qty
                        
                    # 2. Long Duration (> 24h)
                    elif (t2_full - t1_full).total_seconds() > 86400:
                        reason = "LONG_DURATION"
                        ids_to_drop_long.append(tid)
                        pnl_long += pnl
                        qty_long += qty

                    # 3. EOD 17:00-18:00 Gap (NY Time)
                    # Convert to NY time
                    elif purge_overnight:
                        t1_ny = t1_full.astimezone(NY_TZ)
                        t2_ny = t2_full.astimezone(NY_TZ)
                        
                        # Check strictly if open or close is within 17:00:00 - 17:59:59
                        # SC RTH gap Logic
                        if (t1_ny.hour == 17) or (t2_ny.hour == 17):
                            reason = "EOD_1700"
                            ids_to_drop_eod.append(tid)
                            pnl_eod += pnl
                            qty_eod += qty
                except Exception as e:
                    print(f"Error checking trade {tid}: {e}")
                    pass"""

replacement = """            # Optimized SQL-based checks for Future and Long Duration
            ids_to_drop_future, ids_to_drop_long, ids_to_drop_eod = [], [], []
            pnl_future, pnl_long, pnl_eod = 0.0, 0.0, 0.0
            qty_future, qty_long, qty_eod = 0, 0, 0

            now_utc = datetime.datetime.now(datetime.timezone.utc)
            
            # 1. Future Trades (SQL)
            c.execute(f"SELECT trade_id, profit_loss, quantity FROM processed_trades WHERE {base_where} AND entry_time > ?", 
                     base_params + [(now_utc + datetime.timedelta(minutes=5)).isoformat()])
            f_rows = c.fetchall()
            ids_to_drop_future = [r[0] for r in f_rows]
            pnl_future = sum(r[1] for r in f_rows)
            qty_future = sum(r[2] for r in f_rows)

            # 2. Long Duration > 24h (SQL)
            c.execute(f"SELECT trade_id, profit_loss, quantity FROM processed_trades WHERE {base_where} AND (julianday(exit_time) - julianday(entry_time)) > 1.0", 
                     base_params)
            l_rows = c.fetchall()
            ids_to_drop_long = [r[0] for r in l_rows]
            pnl_long = sum(r[1] for r in l_rows)
            qty_long = sum(r[2] for r in l_rows)

            # 3. EOD 17:00-18:00 Gap (NY Time) - Keep in Python for accurate TZ logic, but filter rows first
            if purge_overnight:
                # Only check trades that COULD be in the gap (roughly between 15:00 and 20:00 UTC)
                # To be safe, we just fetch what remains for this account
                c.execute(f"SELECT trade_id, entry_time, exit_time, profit_loss, quantity FROM processed_trades WHERE {base_where}", base_params)
                for tid, t1_str, t2_str, pnl, qty in c.fetchall():
                    if tid in ids_to_drop_future or tid in ids_to_drop_long: continue
                    try:
                        t1 = datetime.datetime.fromisoformat(t1_str).replace(tzinfo=datetime.timezone.utc)
                        t2 = datetime.datetime.fromisoformat(t2_str).replace(tzinfo=datetime.timezone.utc)
                        t1_ny = t1.astimezone(NY_TZ)
                        t2_ny = t2.astimezone(NY_TZ)
                        if (t1_ny.hour == 17) or (t2_ny.hour == 17):
                            ids_to_drop_eod.append(tid)
                            pnl_eod += (float(pnl) if pnl else 0.0)
                            qty_eod += (int(qty) if qty else 0)
                    except: pass"""

if target in text:
    text = text.replace(target, replacement)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS")
else:
    # Try a slightly looser match
    print("FAILED TO MATCH EXACT TEXT")
