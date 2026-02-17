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
        # Range check for Unix micros (2010..2035)
        if 1262304000000000 <= micros <= 2082758400000000:
            return datetime.datetime.fromtimestamp(micros / 1_000_000.0, tz=timezone.utc).astimezone(NY_TZ).replace(tzinfo=None)
        
        # Candidate 2.5: Microseconds since 1899-12-30 (Sierra Chart internal)
        # 2010..2035 range is roughly 3.4e15 to 4.3e15
        if 3400000000000000 <= micros <= 4500000000000000:
            base = datetime.datetime(1899, 12, 30)
            return base + datetime.timedelta(microseconds=micros)
    except Exception:
        pass

    # Candidate 3: Unix epoch in milliseconds - always UTC
    try:
        millis = struct.unpack('<q', value_bytes[:8])[0]
        if 1262304000000 <= millis <= 2082758400000:  # 2010..2035
            return datetime.datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc).astimezone(NY_TZ).replace(tzinfo=None)
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
        
        f_dt = None
        if file_date_match:
            try:
                # Create a 48-hour window around the file date (to handle UTC/Timezone shifts)
                f_dt = datetime.datetime.strptime(file_date_match.group(1), "%Y-%m-%d")
                min_valid_ts = (f_dt - datetime.timedelta(hours=24)).timestamp()
                max_valid_ts = (f_dt + datetime.timedelta(hours=48)).timestamp()
            except: pass

        offset = 0
        file_len = len(d)
        
        current_ts_val = 0
        current_ts_str = None
        base_time = f_dt.timestamp() if f_dt is not None else min_valid_ts
        
        # High-Performance TLV Nitro Loop
        while offset < file_len - 8:
            try:
                # Unpack Tag (4 bytes) and Length (4 bytes)
                tag, length = struct.unpack('<II', d[offset : offset+8])
                
                # Sane check: Tag should be in known range, Length should be plausible
                if tag > 300 or length > 20000000: # 20MB safety cap
                    next_ptr = d.find(b'\x00\x00\x00', offset + 1)
                    if next_ptr == -1: break
                    offset = next_ptr - 1
                    continue

                val_start = offset + 8
                val_end = val_start + length
                if val_end > file_len: break
                    
                if tag == 0x68: # 104: Message String
                    val_bytes = d[val_start : val_end]
                    try:
                        s = val_bytes.decode(errors='ignore')
                        s_lower = s.lower()
                        
                        if any(x in s_lower for x in ["fill", "trade", "bought", "sold", "price", "at", "exec"]):
                            # Improved price regex handles trailing Dots found in binary log
                            pm = re.search(r"(?:lat|price|fillprice|at|last)[:\s]*([\d]+\.?[\d]*)", s_lower)
                            if pm:
                                try: p_val = float(pm.group(1).rstrip('.'))
                                except: p_val = 0
                                
                                if p_val > 0:
                                    side = None
                                    if any(x in s_lower for x in ["buy", "bought", "long"]): side = "BUY"
                                    elif any(x in s_lower for x in ["sell", "sold", "short"]): side = "SELL"
                                    
                                    if not side:
                                        # Bid/Ask proximity side logic for simulation fills
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
                                        
                                        if not current_ts_str:
                                            prog = offset / file_len
                                            dt = datetime.datetime.fromtimestamp(base_time + (prog * 86400))
                                            current_ts_str = dt.isoformat()
                                            current_ts_val = base_time + (prog * 86400)

                                        asym = "Unknown"
                                        s_upper = s.upper()
                                        tm = re.search(r'\b([A-Z]{1,8}[FGHJKMNQUVXZ]\d{1,2})\b', s_upper)
                                        if tm: asym = tm.group(1)
                                        elif sh != "Unknown" and filename_symbol_inferred: asym = sh
                                        elif target_sym and re.search(rf"\b{re.escape(target_sym.upper())}\b", s_upper): 
                                            asym = target_sym.upper()

                                        if target_sym:
                                            if _get_base_symbol_standalone(asym) != target_sym.upper():
                                                offset = val_end
                                                continue
                                        
                                        if asym != "Unknown" and _price_plausible(_get_base_symbol_standalone(asym), p_val):
                                            fills.append({
                                                "account_name": acc, "symbol": asym, "price": p_val, "side": side, 
                                                "quantity": qty, "timestamp": current_ts_str, "ts_val": current_ts_val, "offset": offset
                                            })
                    except: pass
                    
                elif tag == 0x67: # 103: Symbol
                    val_bytes = d[val_start : val_end]
                    try:
                        tsym = val_bytes.decode(errors='ignore').strip('\x00').strip()
                        if tsym: sh, filename_symbol_inferred = tsym, True
                    except: pass
                
                elif tag == 0x66: # 102: Time
                    val_bytes = d[val_start : val_end]
                    parsed_dt = _parse_tag66_timestamp(val_bytes)
                    if parsed_dt is not None:
                        ts_val = parsed_dt.timestamp()
                        if min_valid_ts <= ts_val <= max_valid_ts:
                            current_ts_val, current_ts_str = ts_val, parsed_dt.isoformat()
                
                # Advance strictly to next tag to ensure 100% traversal
                offset = val_end
            except:
                offset += 1
        
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

    async def run_import(self, paths: List[str], filter_symbol: Optional[str] = None, account_filter: Optional[List[str]] = None):
        self.running = True
        self._stop_event = False
        self.stats = {"processed": 0, "found": 0, "errors": 0, "summaries": {}}
        self.progress = 0
        
        try:
            files_to_process = []
            for path in paths:
                if self._stop_event: break
                cp = os.path.normpath(path)
                if os.path.exists(cp):
                    files_to_process.extend(glob.glob(os.path.join(cp, "*.data")))
            
            files_to_process = [f for f in files_to_process if "TradeActivityLog" in os.path.basename(f)]
            acc_set = set()
            if account_filter:
                acc_set = {a.upper() for a in account_filter}
                files_to_process = [f for f in files_to_process if any(acc in os.path.basename(f).upper() for acc in acc_set)]
            elif filter_symbol:
                files_to_process = sorted(list(files_to_process), reverse=True)
            
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
                for i in range(0, total_files, batch_size):
                    if self._stop_event: break
                    batch = files_to_process[i:i+batch_size]
                    self.progress = int((i / total_files) * 60)
                    self.message = f"Ripping: {i}/{total_files} ({self.progress}%)..."
                    
                    loop = asyncio.get_event_loop()
                    tasks = [loop.run_in_executor(executor, partial(_parse_file_nitro, fp, filter_symbol)) for fp in batch]
                    results = await asyncio.gather(*tasks)
                    
                    for res in results:
                        if res: all_fills.extend(res)
                    self.stats["processed"] = min(total_files, i + batch_size)
                    self.stats["found"] = len(all_fills)
                    await asyncio.sleep(0.01)

            if not all_fills:
                self.message = f"Done. No valid trades found in {total_files} files."
                self.running = False
                return

            # Deduplicate fills
            unique_fills_map = {}
            for f in all_fills:
                ts_sec = f['timestamp'][:19]
                key = (f['account_name'], f['symbol'], f['side'], f['price'], f['quantity'], ts_sec)
                if key not in unique_fills_map:
                    unique_fills_map[key] = f
            
            deduped_fills = list(unique_fills_map.values())
            
            self.message = "FIFO Reconstruction..."
            trades = self._pairs_to_trades(deduped_fills)
            
            if not trades:
                self.message = "Could not pair fills."
                self.running = False
                return

            self.message = f"Aggregating split fills for {len(trades)} trades..."
            trades = self._aggregate_trades(trades)
            
            self.message = "Saving to DB..."
            new_count = self._save_trades_to_db(trades)
            
            self.message = "Purging anomalies (Rules 4 & 5)..."
            purge_acc = account_filter[0] if account_filter and len(account_filter) == 1 else None
            self.purge_anomalies(account=purge_acc, symbol=filter_symbol, purge_overnight=True)
            
            self.stats["found"] = new_count
            self.message = f"Import Complete! {new_count} Trades Added."
            
        except Exception as e:
            import traceback
            self.message = f"Nitro Error: {e}"
            print(f"CRITICAL ERROR during import: {e}")
            traceback.print_exc()
        finally:
            self.running = False

    def _pairs_to_trades(self, fills: List[Dict]) -> List[Dict]:
        groups = {}
        for f in fills:
            key = (f['account_name'], f['symbol'])
            if key not in groups: groups[key] = []
            groups[key].append(f)
            
        all_trades = []
        for (acc, specific_sym), group in groups.items():
            base_sym = _get_base_symbol_standalone(specific_sym)
            meta = SYMBOL_METADATA.get(base_sym, {"multiplier": 1, "comm": 4.20})
            multiplier = meta['multiplier']
            commission_per_leg = meta['comm'] / 2.0

            group.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))
            
            buys, sells = [], []
            for f in group:
                qty, side, price, ts = f['quantity'], f['side'], f['price'], f['timestamp']
                
                if side == 'BUY' or side == 'LONG':
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
                    if qty > 0: buys.append({"qty": qty, "price": price, "time": ts})
                else:
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
                    if qty > 0: sells.append({"qty": qty, "price": price, "time": ts})

        return all_trades

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
                    t1 = datetime.datetime.fromisoformat(t['entry_time'])
                    t2 = datetime.datetime.fromisoformat(t['exit_time'])
                    duration = int((t2 - t1).total_seconds() / 60.0)
                    hour, dow = t1.hour, t1.weekday()
                except: duration, hour, dow = 0, 0, 0
                side = "LONG" if "LONG" in t['side'].upper() or "BUY" in t['side'].upper() else "SHORT"
                sig = f"{t['account']}_{t['symbol']}_{t['side']}_{t['entry_time']}_{t['exit_time']}_{t['entry_price']}_{t['exit_price']}_{t['quantity']}"
                tid = "T" + hashlib.md5(sig.encode()).hexdigest()[:12]
                c.execute("""
                    INSERT OR IGNORE INTO processed_trades (
                        trade_id, account_name, symbol, entry_time, exit_time, 
                        entry_price, exit_price, quantity, side, 
                        profit_loss, commission, duration_minutes,
                        hour_of_day, day_of_week
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (tid, t['account'], t['symbol'], t['entry_time'], t['exit_time'],
                      t['entry_price'], t['exit_price'], t['quantity'], side, 
                      t['profit_loss'], t['commission'], duration, hour, dow))
                count += 1
            except: pass
        conn.commit()
        conn.close()
        return count

    def purge_anomalies(self, account: str = None, symbol: Optional[str] = None, purge_overnight: bool = False):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        where_clause, params = [], []
        if account:
            where_clause.append("account_name = ?")
            params.append(account)
        if symbol:
            where_clause.append("symbol = ?")
            params.append(symbol)
        base_where = " AND ".join(where_clause) if where_clause else "1=1"
        results = {"future": 0, "overnight": 0, "outliers": 0, "price_mismatch": 0, "close_boundary": 0}
        limit_date = (datetime.datetime.now() + datetime.timedelta(days=2)).isoformat()
        c.execute(f"DELETE FROM processed_trades WHERE ({base_where}) AND entry_time > ?", params + [limit_date])
        session_cross_where = "CASE WHEN time(entry_time) >= '18:00:00' THEN date(entry_time) ELSE date(entry_time, '-1 day') END != CASE WHEN time(exit_time) >= '18:00:00' THEN date(exit_time) ELSE date(exit_time, '-1 day') END"
        if purge_overnight: c.execute(f"DELETE FROM processed_trades WHERE ({base_where}) AND ({session_cross_where})", params)
        close_cross_where = "date(entry_time) = date(exit_time) AND time(entry_time) < '17:00:00' AND time(exit_time) >= '17:00:00'"
        if purge_overnight: c.execute(f"DELETE FROM processed_trades WHERE ({base_where}) AND ({close_cross_where})", params)
        multiday_where = "date(entry_time) != date(exit_time)"
        if purge_overnight: c.execute(f"DELETE FROM processed_trades WHERE ({base_where}) AND ({multiday_where})", params)
        c.execute(f"DELETE FROM processed_trades WHERE ({base_where}) AND ABS(profit_loss) > 50000", params)
        for sym, meta in SYMBOL_METADATA.items():
            pmin, pmax = meta.get("price_min"), meta.get("price_max")
            if pmin is not None and pmax is not None:
                c.execute(f"DELETE FROM processed_trades WHERE ({base_where}) AND symbol = ? AND (entry_price < ? OR entry_price > ? OR exit_price < ? OR exit_price > ?)", params + [sym, pmin, pmax, pmin, pmax])
        conn.commit()
        conn.close()
        return results

importer = BinaryLogParser()
