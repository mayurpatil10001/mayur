import os
import glob
import re
import datetime
import struct
import asyncio
import sqlite3
import concurrent.futures
from functools import partial
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo

SYMBOL_METADATA = {
    "ES": {"multiplier": 50, "comm": 4.20, "price_min": 500, "price_max": 10000},
    "MES": {"multiplier": 5, "comm": 1.00, "price_min": 50, "price_max": 1000},
    "NQ": {"multiplier": 20, "comm": 4.20, "price_min": 1000, "price_max": 50000},
    "MNQ": {"multiplier": 2, "comm": 1.00, "price_min": 100, "price_max": 5000},
    "CL": {"multiplier": 1000, "comm": 4.20, "price_min": 20, "price_max": 200},
    "MCL": {"multiplier": 100, "comm": 1.00, "price_min": 20, "price_max": 200},
    "FDAX": {"multiplier": 25, "comm": 3.00, "price_min": 1000, "price_max": 50000},
    "RTY": {"multiplier": 50, "comm": 4.20, "price_min": 200, "price_max": 5000},
    "M2K": {"multiplier": 5, "comm": 1.00, "price_min": 20, "price_max": 500},
    "GC": {"multiplier": 100, "comm": 4.20, "price_min": 500, "price_max": 5000},
    "SI": {"multiplier": 5000, "comm": 4.20, "price_min": 5, "price_max": 100},
    "YM": {"multiplier": 5, "comm": 4.20, "price_min": 5000, "price_max": 100000},
    "MYM": {"multiplier": 0.5, "comm": 1.00, "price_min": 500, "price_max": 10000},
}

NY_TZ = ZoneInfo("America/New_York")
SESSION_CLOSE_HOUR_NY = 17
SESSION_CUTOFF_HOUR_NY = 18

def _get_base_symbol_standalone(raw: str) -> str:
    s = raw.upper()
    match = re.search(r'([A-Z]+)', s)
    if not match: return s
    base = match.group(1)
    m = {'CLN': 'CL', 'CLH': 'CL', 'CLQ': 'CL', 'CLU': 'CL', 'CLV': 'CL', 'CLZ': 'CL',
         'ESM': 'ES', 'ESU': 'ES', 'ESZ': 'ES', 'ESH': 'ES',
         'NQM': 'NQ', 'NQU': 'NQ', 'NQZ': 'NQ', 'NQH': 'NQ'}
    if base in m: return m[base]
    for p in SYMBOL_METADATA.keys():
        if base.startswith(p): return p
    return base


def _price_plausible(symbol: str, price: float) -> bool:
    meta = SYMBOL_METADATA.get(symbol)
    if not meta:
        return True
    pmin = meta.get("price_min")
    pmax = meta.get("price_max")
    if pmin is None or pmax is None:
        return True
    return pmin <= price <= pmax


def _to_ny(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        # Default to wall-clock NY if no tz info (common for SC local logs)
        return dt.replace(tzinfo=NY_TZ)
    return dt.astimezone(NY_TZ)


def _parse_tag66_timestamp(value_bytes: bytes) -> Optional[datetime.datetime]:
    """
    Decode SC timestamp candidates from Tag 0x66 payload.
    Returns naive datetime in local wall-clock representation.
    """
    from datetime import timezone
    if len(value_bytes) < 8:
        return None

    # Candidate 1: SCDateTime double (days since 1899-12-30) - usually local time
    try:
        val = struct.unpack('<d', value_bytes[:8])[0]
        if 30000 < val < 70000:
            base = datetime.datetime(1899, 12, 30)
            dt = base + datetime.timedelta(days=val)
            if 2010 <= dt.year <= 2035:
                # SCDateTime is wall-clock time
                return dt
    except Exception:
        pass

    # Candidate 2: Unix epoch in microseconds - always UTC
    try:
        micros = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000000 <= micros <= 2082758400000000:
            return datetime.datetime.fromtimestamp(micros / 1_000_000.0, tz=timezone.utc).replace(tzinfo=None)
        
        if 3400000000000000 <= micros <= 4500000000000000:
            base = datetime.datetime(1899, 12, 30)
            return base + datetime.timedelta(microseconds=micros)
    except Exception:
        pass

    # Candidate 3: Unix epoch in milliseconds - always UTC
    try:
        millis = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000 <= millis <= 2082758400000:
            return datetime.datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        pass
    return None


def _session_trade_date_ny(dt: datetime.datetime) -> datetime.date:
    """
    Standard Sierra Chart Trade Date logic:
    Session rolls over at 17:00 NY (EOD Close).
    - Mon 16:59 -> Monday Session
    - Mon 17:01 -> Tuesday Session
    """
    ny = _to_ny(dt)
    if ny.hour >= 17:
        return (ny + datetime.timedelta(days=1)).date()
    return ny.date()


def _crosses_daily_close_ny(entry_dt: datetime.datetime, exit_dt: datetime.datetime) -> bool:
    """
    Returns True if a trade crosses the daily close boundary at 17:00 NY.
    Rule requested: drop trades that start before 17:00 and close after 17:00.
    """
    e = _to_ny(entry_dt)
    x = _to_ny(exit_dt)
    if x <= e:
        return False

    # Check each candidate close boundary in the time span.
    day = e.date()
    last_day = x.date()
    while day <= last_day:
        close_boundary = datetime.datetime(
            day.year, day.month, day.day, SESSION_CLOSE_HOUR_NY, 0, 0, tzinfo=NY_TZ
        )
        if e < close_boundary <= x:
            return True
        day += datetime.timedelta(days=1)
    return False

def _parse_file_nitro(fp: str, target_sym: Optional[str] = None) -> List[Dict]:
    fills = []
    try:
        fn = os.path.basename(fp).upper()
        if os.path.getsize(fp) == 0: return []
        
        with open(fp, "rb") as bf:
            # Limit read to 200MB per file to prevent RAM blowout in parallel
            d = bf.read(200 * 1024 * 1024) 

        pts = fn.split('.')
        acc = re.sub(r'_UTC$', '', pts[-2] if len(pts) > 1 else fn)
        # Priority 1: Use provided target symbol as the primary context if available
        sh = target_sym.upper() if target_sym else "Unknown"
        filename_symbol_inferred = True if target_sym else False
        
        # Priority 2: Refine from filename if possible
        for s in SYMBOL_METADATA.keys():
            if re.search(rf"[._]{s}[.\-_]", fn) or fn.startswith(f"{s}-") or acc.startswith(f"{s}_"):
                sh = s
                filename_symbol_inferred = True
                break
        
        # Root Cause Fix: Extract Date from Filename to Lock Timestamp Window
        file_date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fn)
        min_valid_ts, max_valid_ts = 1600000000, 2000000000
        
        if file_date_match:
            try:
                f_dt = datetime.datetime.strptime(file_date_match.group(1), "%Y-%m-%d")
            except: pass

        offset = 0
        file_len = len(d)
        seen_keys = set()
        
        # High-Performance TLV Nitro Loop
        pending_fill = None
        current_ts_val = 0
        current_ts_str = None
        # Default fallback is the date in the filename (start of UTC day)
        base_time = f_dt.timestamp() if f_dt else datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        
        while offset < file_len - 8:
            try:
                # Unpack Tag (4 bytes) and Length (4 bytes)
                tag, length = struct.unpack('<II', d[offset : offset+8])
                
                # Sane check: Tag should be in known range, Length should be plausible
                if tag > 500 or length > 20000000: # 20MB safety cap
                    next_ptr = d.find(b'\x00\x00\x00', offset + 1)
                    if next_ptr == -1: break
                    offset = next_ptr - 1
                    continue

                val_start = offset + 8
                val_end = val_start + length
                if val_end > file_len: break
                
                if tag == 0x66: # 102: Time: Start of a new record/event
                    if pending_fill:
                        # Deduplicate before committing
                        pf = pending_fill
                        fill_key = f"{pf['account_name']}_{pf['symbol']}_{pf['order_id']}_{pf['price']}_{pf['side']}" if pf['order_id'] else f"{pf['account_name']}_{pf['symbol']}_{round(pf['ts_val'], 3)}_{pf['price']}_{pf['side']}_{pf['quantity']}"
                        if fill_key not in seen_keys:
                            fills.append(pf)
                            seen_keys.add(fill_key)
                        pending_fill = None
                    
                    parsed_dt = _parse_tag66_timestamp(d[val_start:val_end])
                    if parsed_dt is not None:
                         current_ts_val, current_ts_str = parsed_dt.timestamp(), parsed_dt.isoformat()
                
                elif tag == 0x67: # 103: Symbol
                    tsym = d[val_start:val_end].decode(errors='ignore').strip('\x00').strip()
                    if tsym: sh, filename_symbol_inferred = tsym, True
                
                elif tag == 100 or tag == 124: # OrderID / ServiceOrderID
                    try:
                        oid = d[val_start:val_end].decode(errors='ignore').strip()
                        if oid and pending_fill: pending_fill['order_id'] = oid
                    except: pass
                    
                elif tag == 0x68: # 104: Message String
                    val_bytes = d[val_start : val_end]
                    s = val_bytes.decode(errors='ignore')
                    s_lower = s.lower()
                    
                    if ("trade simulation fill" in s_lower or "fill: " in s_lower) and "updated internal position" not in s_lower:
                        pm = re.search(r"(?:lat|price|fillprice|at|last)[:\s]*([\d]+\.?[\d]*)", s_lower)
                        if pm:
                            try: p_val = float(pm.group(1).rstrip('.'))
                            except: p_val = 0
                            
                            if p_val > 0:
                                side = None
                                if any(x in s_lower for x in ["buy", "bought", "long"]): side = "BUY"
                                elif any(x in s_lower for x in ["sell", "sold", "short"]): side = "SELL"
                                
                                if not side:
                                    bm = re.search(r"bid[:\s]*([\d]+\.?[\d]*)", s_lower)
                                    am = re.search(r"ask[:\s]*([\d]+\.?[\d]*)", s_lower)
                                    lm = re.search(r"last[:\s]*([\d]+\.?[\d]*)", s_lower)
                                    if bm and am and lm:
                                        try:
                                            bid = float(bm.group(1).rstrip('.'))
                                            ask = float(am.group(1).rstrip('.'))
                                            last = float(lm.group(1).rstrip('.'))
                                            side = "BUY" if abs(last - ask) < abs(last - bid) else "SELL"
                                        except: pass
                                
                                if side:
                                    qty = 1
                                    qm = re.search(r"(?:qty|quantity|size|fill qty|q:|vol)\s*:?\s*(\d+)", s_lower)
                                    if qm:
                                        try: qty = int(qm.group(1))
                                        except: qty = 1
                                    else:
                                        qm2 = re.search(r"(?:buy|sell|bought|sold|long|short)\s+(\d+)", s_lower)
                                        if qm2: 
                                            try: qty = int(qm2.group(1))
                                            except: qty = 1
                                    
                                    order_id = None
                                    om = re.search(r"internalorderid[:\s]*(\d+)", s_lower)
                                    if om: order_id = om.group(1)
                                    
                                    if not current_ts_str:
                                        dt = datetime.datetime.fromtimestamp(base_time)
                                        current_ts_str, current_ts_val = dt.isoformat(), base_time

                                    asym = "Unknown"
                                    s_upper = s.upper()
                                    tm = re.search(r'\b([A-Z]{1,8}[FGHJKMNQUVXZ]\d{1,2})\b', s_upper)
                                    if tm: asym = tm.group(1)
                                    elif sh != "Unknown" and filename_symbol_inferred: asym = sh
                                    elif target_sym and re.search(rf"\b{re.escape(target_sym.upper())}\b", s_upper): asym = target_sym.upper()

                                    if target_sym and _get_base_symbol_standalone(asym) != target_sym.upper():
                                        offset = val_end
                                        continue
                                    
                                    if asym != "Unknown" and _price_plausible(_get_base_symbol_standalone(asym), p_val):
                                        pending_fill = {
                                            "account_name": acc, "symbol": asym, "price": p_val, "side": side, 
                                            "quantity": qty, "timestamp": current_ts_str, "ts_val": current_ts_val, "offset": offset,
                                            "order_id": order_id
                                        }
                    
                elif tag == 126 and pending_fill:
                    try:
                        v = struct.unpack('<i', d[val_start:val_start+4])[0]
                        if v > 0: pending_fill['quantity'] = v
                    except: pass
                elif tag in [108, 114] and pending_fill and pending_fill['quantity'] == 1:
                    try:
                        v = int(struct.unpack('<d', d[val_start:val_start+8])[0])
                        if v > 0: pending_fill['quantity'] = v
                    except: pass

                # Advance strictly to next tag to ensure 100% traversal
                offset = val_end
            except:
                break # Exit loop on parsing error to prevent infinite loop
        
        # Final flush of any pending fill after the loop finishes
        if pending_fill:
            pf = pending_fill
            fill_key = f"{pf['account_name']}_{pf['symbol']}_{pf['order_id']}_{pf['price']}_{pf['side']}" if pf['order_id'] else f"{pf['account_name']}_{pf['symbol']}_{round(pf['ts_val'], 3)}_{pf['price']}_{pf['side']}_{pf['quantity']}"
            if fill_key not in seen_keys:
                fills.append(pf)
                seen_keys.add(fill_key)

        if sh == "Unknown" and target_sym:
            sh = target_sym.upper()
            filename_symbol_inferred = True

        with open("import_debug.log", "a") as fld:
            fld.write(f"FILE: {fn} | ACC: {acc} | SYMBOL: {sh} | FILLS: {len(fills)}\n")

    except Exception as e:
        with open("import_debug.log", "a") as fld:
            fld.write(f"ERROR: {os.path.basename(fp)} -> {str(e)}\n")
            
    return fills

class BinaryLogParser:
    def __init__(self, db_path=None):
        if db_path is None:
            from pathlib import Path
            self.db_path = str(Path(__file__).parent.parent.parent / 'trading_platform.db')
        else:
            self.db_path = db_path
        self.running = False
        self.stats = {"processed": 0, "found": 0, "errors": 0, "summaries": {}}
        self.message = "Idle"
        self.progress = 0
        self._stop_event = False
        self._ensure_schema()

    def _ensure_schema(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS processed_trades (
                trade_id TEXT PRIMARY KEY,
                account_name TEXT,
                symbol TEXT,
                entry_time TEXT,
                exit_time TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity INTEGER,
                side TEXT,
                profit_loss REAL,
                commission REAL,
                duration_minutes INTEGER,
                hour_of_day INTEGER,
                day_of_week INTEGER
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_proc_trades_acc_sym ON processed_trades(account_name, symbol)")
        conn.commit()
        conn.close()

    def stop(self):
        self._stop_event = True
        self.message = "Stopping..."

    async def run_import(self, paths: List[str], filter_symbol: Optional[str] = None, account_filter: Optional[List[str]] = None, days_lookback: Optional[int] = None):
        self.running = True
        self._stop_event = False
        self.stats = {"processed": 0, "found": 0, "errors": 0, "summaries": {}}
        self.progress = 0
        
        try:
            files_to_process = []
            cutoff_time = None
            if days_lookback:
                cutoff_time = (datetime.datetime.now() - datetime.timedelta(days=days_lookback)).timestamp()

            for path in paths:
                if self._stop_event: break
                cp = os.path.normpath(path)
                print(f"DEBUG: Checking path: '{cp}' Exists: {os.path.exists(cp)}")
                if os.path.exists(cp):
                    all_data_files = glob.glob(os.path.join(cp, "*.data")) + glob.glob(os.path.join(cp, "*.DATA"))
                    # Deduplicate in case of case-insensitive filesystem
                    all_data_files = list(set(all_data_files))
                    if cutoff_time:
                        all_data_files = [f for f in all_data_files if os.path.getmtime(f) >= cutoff_time]
                    files_to_process.extend(all_data_files)
            
            files_to_process = sorted(list(files_to_process))
            print(f"DEBUG: Found {len(files_to_process)} files after glob.")
            
            files_to_process = [f for f in files_to_process if "TradeActivityLog" in os.path.basename(f)]
            print(f"DEBUG: {len(files_to_process)} files after name filter.")

            if account_filter:
                acc_set = {a.upper() for a in account_filter}
                files_to_process = [f for f in files_to_process if any(acc in os.path.basename(f).upper() for acc in acc_set)]
                print(f"DEBUG: {len(files_to_process)} files after account filter {acc_set}.")
            
            # ALWAYS sort files by name/date to ensure logical FIFO ordering during pairing
            files_to_process = sorted(list(files_to_process))
            
            with open("import_files_trace.log", "w") as ftrace:
                ftrace.write(f"Scanned {len(files_to_process)} files.\n")
                for f in files_to_process:
                     ftrace.write(f"QUEUED: {f} | Mtime: {os.path.getmtime(f)}\n")
            
            total_files = len(files_to_process)
            if total_files == 0:
                self.message = "No matching logs found."
                self.running = False
                return

            self.message = f"Starting Multi-Core Engine ({total_files} files)..."
            all_fills = []
            max_workers = max(1, (os.cpu_count() or 4) - 1)
            
            with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
                batch_size = 50
                all_unique_fills = {} # Initialize all_unique_fills
                for i in range(0, total_files, batch_size):
                    if self._stop_event: break
                    batch = files_to_process[i:i+batch_size]
                    self.progress = int((i / total_files) * 60)
                    self.message = f"Ripping: {i}/{total_files} ({self.progress}%)..."
                    
                    loop = asyncio.get_event_loop()
                    # _parse_file_nitro is a global helper function
                    tasks = [loop.run_in_executor(executor, partial(_parse_file_nitro, fp, filter_symbol)) for fp in batch]
                    
                    for f_task in await asyncio.gather(*tasks):
                        res = f_task
                        if res:
                            all_fills.extend(res)
                            # Generate unique_fills_map logic inline or just extend all_fills
                            for f in res:
                                # Fuzzy Deduplication: Round to seconds to handle Instance Jitter (1-second window)
                                # Ignore OrderID in the key since some messages for the same fill have it and others don't
                                ts_key = f['timestamp'][:19]
                                key = (f['account_name'], f['symbol'], f['side'], f['price'], f['quantity'], ts_key)
                                if key not in all_unique_fills:
                                    all_unique_fills[key] = f

                    self.stats["processed"] = min(total_files, i + batch_size)
                    self.stats["found"] = len(all_fills)
                    await asyncio.sleep(0.01)

            if not all_fills:
                self.message = f"Done. No valid trades found in {total_files} files."
                self.running = False
                return

            # Use the unique fills collected in the loop
            deduped_fills = list(all_unique_fills.values())
            
            self.message = "FIFO Reconstruction..."
            trades, unpaired = self._pairs_to_trades(deduped_fills, persist_state=True)
            
            if not trades and not unpaired:
                self.message = "No fills found to process."
                self.running = False
                return

            self.message = f"Aggregating split fills for {len(trades)} trades..."
            trades = self._aggregate_trades(trades)
            
            self.message = "Saving to DB..."
            new_count = self._save_trades_to_db(trades)
            
            # Debug Trace: Did we actually save any Feb 17 trades for SIM15?
            sim15_feb17 = [t for t in trades if t['account'].upper() == '3Q_SIM15' and '2026-02-17' in t['entry_time']]
            with open("import_debug.log", "a") as fld:
                fld.write(f"FINAL SAVE CHECK: 3Q_SIM15 Feb 17 trades in list: {len(sim15_feb17)}\n")
            
            self.message = "Applying Shield Rules (Purging Anomalies)..."
            # Always purge all accounts involved in the import session
            breakdown = self.purge_anomalies(account=None, symbol=filter_symbol, purge_overnight=True)
            
            # Aggregate stats across all accounts
            total_future = sum(b.get("future", {}).get("count", 0) for b in breakdown.values())
            total_long_duration = sum(b.get("long_duration", {}).get("count", 0) for b in breakdown.values())
            total_outliers = sum(b.get("outliers", {}).get("count", 0) for b in breakdown.values())
            total_eod_1700 = sum(b.get("eod_1700", {}).get("count", 0) for b in breakdown.values())
            total_price_mismatch = sum(b.get("price_mismatch", {}).get("count", 0) for b in breakdown.values())
            
            total_dropped = total_future + total_long_duration + total_outliers + total_eod_1700 + total_price_mismatch
            attempted = new_count + total_dropped
            drop_pct = round((total_dropped / attempted * 100), 1) if attempted > 0 else 0
            
            # Final Stats Update
            self.stats["found"] = new_count
            self.stats["unpaired_fills"] = unpaired
            self.stats["dropped_long_duration"] = total_long_duration
            self.stats["dropped_eod_1700"] = total_eod_1700
            self.stats["dropped_outliers"] = total_outliers
            self.stats["dropped_pct"] = drop_pct
            self.stats["breakdown"] = breakdown
            
            self.message = f"Import Complete! Added: {new_count} | Dropped: {total_dropped} ({drop_pct}%) | Open: {unpaired} fills"
            
            with open("import_debug.log", "a") as fld:
                fld.write(f"SUMMARY: Added {new_count}, Dropped {total_dropped} ({drop_pct}%), Unpaired (Open) {unpaired}\n")
                fld.write(f"BREAKDOWN: {str(breakdown)}\n")
            
        except Exception as e:
            import traceback
            self.message = f"Nitro Error: {e}"
            print(f"CRITICAL ERROR during import: {e}")
            traceback.print_exc()
        finally:
            self.running = False

    def _pairs_to_trades(self, fills: List[Dict], persist_state: bool = True) -> (List[Dict], int):
        conn = sqlite3.connect(self.db_path)
        # conn.row_factory = sqlite3.Row # Dict access
        
        groups = {}
        for f in fills:
            key = (f['account_name'], f['symbol'])
            if key not in groups: groups[key] = []
            groups[key].append(f)
            
        all_trades = []
        unpaired_count = 0
        
        try:
            for (acc, specific_sym), group in groups.items():
                base_sym = _get_base_symbol_standalone(specific_sym)
                
                # 1. LOAD PENDING FILLS (Stateful)
                if persist_state:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT side, entry_time, price, quantity FROM pending_fills WHERE account_name = ? AND symbol = ? ORDER BY created_at ASC",
                        (acc, base_sym)
                    )
                    rows = cursor.fetchall()
                    # Convert back to fill dicts
                    pending = []
                    for r in rows:
                        # r: (side, entry_time, price, quantity)
                        # We need to adapt them to the loop structure
                        # The loop expects: qty, side, price, ts, ts_val
                        # We'll construct a pseudo-fill
                        side_u = r[0].upper()
                        ts_str = r[1]
                        
                        ts_val = 0
                        try:
                            dt = datetime.datetime.fromisoformat(ts_str)
                            ts_val = dt.timestamp()
                        except: pass
                        
                        # We put them in the group? Or pre-populate buys/sells?
                        # Pre-populating buys/sells is safer essentially.
                        # But the loop iterates 'group'.
                        # Let's add them to 'group' and let the sort handle order?
                        # Yes, if we trust timestamps.
                        
                        pending.append({
                            "account_name": acc, "symbol": specific_sym, # Use specific?
                            "side": side_u, "quantity": r[3], "price": r[2], 
                            "timestamp": ts_str, "ts_val": ts_val,
                            "offset": -1 # Priority
                        })
                    
                    # Merge pending into group
                    group.extend(pending)

                meta = SYMBOL_METADATA.get(base_sym, {"multiplier": 1, "comm": 4.20})
                multiplier = meta['multiplier']
                commission_per_leg = meta['comm'] / 2.0

                group.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))
                
                buys, sells = [], []
                for f in group:
                    qty, side, price, ts = f['quantity'], f['side'], f['price'], f['timestamp']
                    ts_val = f.get('ts_val', 0)
                    
                    if side == 'BUY' or side == 'LONG':
                        # Skip stale sells (> 24h)
                        # sells = [s for s in sells if ts_val - s['ts_val'] < 86400] 
                        # DISABLE STALE CHECK for stateful logic? No, keep it but maybe relax?
                        # If we carry forward, we want to match even if > 24h? 
                        # For now keep 24h rule to avoid matching ancient noise.
                        sells = [s for s in sells if ts_val - s['ts_val'] < 86400]
                        
                        while qty > 0 and sells:
                            s = sells[0]
                            match_qty = min(qty, s['qty'])
                            pnl = (s['price'] - price) * match_qty * multiplier
                            total_comm = round(match_qty * (commission_per_leg * 2), 2)
                            all_trades.append({
                                "account": acc, "symbol": base_sym, "side": "SHORT",
                                "entry_time": s['time'], "exit_time": ts, 
                                "entry_price": s['price'], "exit_price": price,
                                "quantity": int(match_qty), "profit_loss": round(pnl - total_comm, 2),
                                "commission": total_comm
                            })
                            qty -= match_qty
                            s['qty'] -= match_qty
                            if s['qty'] <= 0: sells.pop(0)
                        if qty > 0: buys.append({"qty": qty, "price": price, "time": ts, "ts_val": ts_val})
                    else:
                        # Skip stale buys (> 24h)
                        buys = [b for b in buys if ts_val - b['ts_val'] < 86400]
                        while qty > 0 and buys:
                            b = buys[0]
                            match_qty = min(qty, b['qty'])
                            pnl = (price - b['price']) * match_qty * multiplier
                            total_comm = round(match_qty * (commission_per_leg * 2), 2)
                            all_trades.append({
                                "account": acc, "symbol": base_sym, "side": "LONG",
                                "entry_time": b['time'], "exit_time": ts,
                                "entry_price": b['price'], "exit_price": price,
                                "quantity": int(match_qty), "profit_loss": round(pnl - total_comm, 2),
                                "commission": total_comm
                            })
                            qty -= match_qty
                            b['qty'] -= match_qty
                            if b['qty'] <= 0: buys.pop(0)
                        if qty > 0: sells.append({"qty": qty, "price": price, "time": ts, "ts_val": ts_val})
                
                unpaired_count += sum(b['qty'] for b in buys)
                unpaired_count += sum(s['qty'] for s in sells)
                
                # 2. SAVE REMAINING AS PENDING (Stateful)
                if persist_state:
                    cursor = conn.cursor()
                    # Clear old for this bucket
                    cursor.execute("DELETE FROM pending_fills WHERE account_name = ? AND symbol = ?", (acc, base_sym))
                    
                    # Insert new leftovers
                    # Buys
                    for b in buys:
                        cursor.execute(
                            "INSERT INTO pending_fills (account_name, symbol, side, entry_time, price, quantity) VALUES (?, ?, ?, ?, ?, ?)",
                            (acc, base_sym, 'BUY', b['time'], b['price'], b['qty'])
                        )
                    # Sells
                    for s in sells:
                        cursor.execute(
                            "INSERT INTO pending_fills (account_name, symbol, side, entry_time, price, quantity) VALUES (?, ?, ?, ?, ?, ?)",
                            (acc, base_sym, 'SELL', s['time'], s['price'], s['qty'])
                        )
                    conn.commit()

        finally:
            conn.close()

        return all_trades, int(unpaired_count)

    def _aggregate_trades(self, trades: List[Dict]) -> List[Dict]:
        if not trades: return []
        trades.sort(key=lambda x: x['entry_time'])
        def make_key(t):
            return (t['account'], t['symbol'], t['side'], t['entry_time'], t['exit_time'], t['entry_price'], t['exit_price'])
        grouped = {}
        for t in trades:
            k = make_key(t)
            if k not in grouped: grouped[k] = t.copy()
            else:
                existing = grouped[k]
                existing['quantity'] += t['quantity']
                existing['profit_loss'] += t['profit_loss']
                existing['commission'] += t['commission']
        aggregated = sorted(list(grouped.values()), key=lambda x: x['entry_time'])
        return aggregated

    def _save_trades_to_db(self, trades: List[Dict]) -> int:
        if not trades: return 0
        import hashlib
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        count = 0
        for t in trades:
            try:
                try:
                    t1_utc = datetime.datetime.fromisoformat(t['entry_time']).replace(tzinfo=datetime.timezone.utc)
                    t2_utc = datetime.datetime.fromisoformat(t['exit_time']).replace(tzinfo=datetime.timezone.utc)
                    duration = int((t2_utc - t1_utc).total_seconds() / 60.0)
                    
                    # Store hour and day of week in New York time for session analysis
                    t1_ny = t1_utc.astimezone(NY_TZ)
                    hour, dow = t1_ny.hour, t1_ny.weekday()
                except: duration, hour, dow = 0, 0, 0
                side = "LONG" if "LONG" in t['side'].upper() or "BUY" in t['side'].upper() else "SHORT"
                acc_upper = t['account'].upper()
                sym_upper = t['symbol'].upper()
                sig = f"{acc_upper}_{sym_upper}_{side}_{t['entry_time']}_{t['exit_time']}_{t['entry_price']}_{t['exit_price']}_{t['quantity']}"
                tid = "T" + hashlib.md5(sig.encode()).hexdigest()[:12]
                c.execute("""
                    INSERT OR IGNORE INTO processed_trades (
                        trade_id, account_name, symbol, entry_time, exit_time, 
                        entry_price, exit_price, quantity, side, 
                        profit_loss, commission, duration_minutes,
                        hour_of_day, day_of_week
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (tid, acc_upper, sym_upper, t['entry_time'], t['exit_time'],
                      t['entry_price'], t['exit_price'], t['quantity'], side, 
                      t['profit_loss'], t['commission'], duration, hour, dow))
                count += 1
                         
            except Exception as e:
                with open("db_error.log", "a") as err:
                    err.write(f"DB Error for {tid}: {e}\n")
        conn.commit()
        conn.close()
        return count

    def purge_anomalies(self, account: str = None, symbol: Optional[str] = None, purge_overnight: bool = False):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Determine which accounts to process
        if account:
            accounts = [account]
        else:
            c.execute("SELECT DISTINCT account_name FROM processed_trades")
            accounts = [r[0] for r in c.fetchall()]
            
        where_symbol = " AND symbol LIKE ? || '%'" if symbol else ""
        params_symbol = [symbol] if symbol else []
        
        # Structure: { account_name: { rule_name: { count: int, pnl: float } } }
        breakdown = {}
        for acc in accounts:
            acc_breakdown = {
                "future": {"count": 0, "pnl": 0.0, "qty": 0},
                "long_duration": {"count": 0, "pnl": 0.0, "qty": 0}, 
                "outliers": {"count": 0, "pnl": 0.0, "qty": 0}, 
                "eod_1700": {"count": 0, "pnl": 0.0, "qty": 0}, 
                "price_mismatch": {"count": 0, "pnl": 0.0, "qty": 0}
            }
            base_where = "account_name = ?" + where_symbol
            base_params = [acc] + params_symbol
            
            # Fetch all trades to filter in Python
            
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
                    pass

            # Log deletions for debugging
            if ids_to_drop_future or ids_to_drop_long or ids_to_drop_eod:
                print(f"DEBUG: EXECUTION CONFIRMED - Purging {len(ids_to_drop_eod)} EOD trades for {acc}")
                with open("import_debug.log", "a") as f:
                    f.write(f"PURGE {acc}: Future={len(ids_to_drop_future)} (${pnl_future:.2f}) | Long={len(ids_to_drop_long)} (${pnl_long:.2f}) | EOD={len(ids_to_drop_eod)} (${pnl_eod:.2f})\n")
                    f.write(f"TOTAL DROPPED PNL for {acc}: {(pnl_future + pnl_long + pnl_eod):.2f}\n")
                    if ids_to_drop_eod:
                         f.write(f"SAMPLE EOD DROP: {ids_to_drop_eod[:3]}\n")

            def delete_batch(ids):
                if not ids: return 0
                chunk_size = 500
                count = 0
                for i in range(0, len(ids), 500):
                    chunk = ids[i:i+500]
                    placeholders = ",".join(["?"] * len(chunk))
                    c.execute(f"DELETE FROM processed_trades WHERE trade_id IN ({placeholders})", chunk)
                    count += c.rowcount
                return count

            acc_breakdown["future"]["count"] = delete_batch(ids_to_drop_future)
            acc_breakdown["future"]["pnl"] = pnl_future
            acc_breakdown["future"]["qty"] = qty_future
            
            acc_breakdown["long_duration"]["count"] = delete_batch(ids_to_drop_long)
            acc_breakdown["long_duration"]["pnl"] = pnl_long
            acc_breakdown["long_duration"]["qty"] = qty_long
            
            acc_breakdown["eod_1700"]["count"] = delete_batch(ids_to_drop_eod)
            acc_breakdown["eod_1700"]["pnl"] = pnl_eod
            acc_breakdown["eod_1700"]["qty"] = qty_eod
            
            # 4. Statistical PnL Outliers (Drop)
            # Use Z-score logic per symbol: Mean + X * StdDev
            # We calculate this specifically for the symbol context to avoid bias
            symbol_list = []
            if symbol:
                symbol_list = [symbol]
            else:
                c.execute("SELECT DISTINCT symbol FROM processed_trades WHERE account_name = ?", (acc,))
                symbol_list = [r[0] for r in c.fetchall()]

            for sym in symbol_list:
                # Calculate stats for this sym/acc
                c.execute(
                    "SELECT AVG(profit_loss), AVG(profit_loss * profit_loss) - (AVG(profit_loss) * AVG(profit_loss)) as variance "
                    "FROM processed_trades WHERE account_name = ? AND symbol = ?", 
                    (acc, sym)
                )
                row = c.fetchone()
                if row and row[0] is not None:
                    avg_pnl = row[0]
                    # StdDev = sqrt(variance)
                    std_dev = (row[1] ** 0.5) if row[1] > 0 else 0
                    
                    # Statistical Threshold: 5 Sigma (Very conservative, but will catch the $21k Jan spike)
                    # For a normal distribution, 5 sigma is 1 in 3.5 million. 
                    # For trading, it's roughly 4-6 sigma for "lottery" moves.
                    sigma_multiplier = 5.0
                    upper_bound = avg_pnl + (sigma_multiplier * std_dev)
                    lower_bound = avg_pnl - (sigma_multiplier * std_dev)
                    
                    # We also add a minimum floor ($4,000) so we don't prune small-variance strategies
                    final_upper = max(upper_bound, 4000)
                    final_lower = min(lower_bound, -4000)

                    c.execute(
                        "SELECT trade_id, profit_loss FROM processed_trades "
                        "WHERE account_name = ? AND symbol = ? AND (profit_loss > ? OR profit_loss < ?)",
                        (acc, sym, final_upper, final_lower)
                    )
                    outliers_to_drop = c.fetchall()
                    
                    if outliers_to_drop:
                        ids = [o[0] for o in outliers_to_drop]
                        pnl_sum = sum(o[1] for o in outliers_to_drop)
                        
                        dropped_count = delete_batch(ids)
                        acc_breakdown["outliers"]["count"] += dropped_count
                        acc_breakdown["outliers"]["pnl"] += pnl_sum
                        
                        with open("import_debug.log", "a") as f:
                            f.write(f"PURGE {acc} [{sym}]: Outliers={dropped_count} (${pnl_sum:.2f}) | Thresholds: {final_lower:.0f} to {final_upper:.0f}\n")
            
            # 5. Price Mismatches (Drop)
            # PnL for bad price is not calculated/needed as per requirement
            for sym, meta in SYMBOL_METADATA.items():
                pmin, pmax = meta.get("price_min"), meta.get("price_max")
                if pmin is not None and pmax is not None:
                    # Just count, no PnL calc for bad price as requested
                    c.execute(f"DELETE FROM processed_trades WHERE ({base_where}) AND symbol = ? AND (entry_price < ? OR entry_price > ? OR exit_price < ? OR exit_price > ?)", base_params + [sym, pmin, pmax, pmin, pmax])
                    acc_breakdown["price_mismatch"]["count"] += c.rowcount
            
            breakdown[acc] = acc_breakdown
            
        conn.commit()
        conn.close()
        return breakdown

importer = BinaryLogParser()
