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
from ..utils.timezone_utils import NY_TZ

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

# NY_TZ imported from timezone_utils
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

def _is_ghost_fill(acc: str, note: str, ts_str: str, msgtxt: str = "", is_open: bool = True, qty: float = 0) -> bool:
    """
    Returns True if the fill should be dropped as a "Ghost".
    Rule: All accounts require an Order Note (Tag 0x82) OR must be EOD (16:55-17:05 NY).
    If message contains "Text: Tag" / "Tag: AT_", SC embedded the strategy tag in the message (valid).
    EXCEPT: Do NOT discard if it's a CLOSE (is_open=False), as these are often real stops.
    """
    # Universal Exemption: 1-lots are almost always legitimate stop-outs or automated trades.
    # The known massive ghosts (e.g. 04:05) are multi-lot.
    with open("ghost_all.log", "a") as f:
        f.write(f"DEBUG GHOST: ts={ts_str}, is_open={is_open}, qty={qty}, note='{note}', msg='{msgtxt}'\n")
    if qty == 1:
        return False

    note_u = (note or "").strip()
    msg_l = (msgtxt or "").lower()

    # EOD Exception (16:55 - 17:05 NY) for session flattenings
    # These often lack strategy tags and must never be considered ghosts.
    try:
        dt_obj = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=datetime.timezone.utc)
        ny = dt_obj.astimezone(NY_TZ)
        if (ny.hour == 16 and ny.minute >= 55) or (ny.hour == 17 and ny.minute <= 5):
            return False
    except:
        pass

    # Rule: If it's a "Trading Evaluator" Filled record, it MUST have a strategy tag
    # either in the Note or in the Message Text.
    # 04:05 Ghost: msg contains "Trading Evaluator (Filled)" but no strategy tag.
    # We apply this even if is_open=False because SC often marks ghosts as CLOSE.
    if "trading evaluator" in msg_l and "filled" in msg_l:
        # Robust tag detection: Look for "AT_" anywhere in msg if it follows "Tag" or similar.
        has_tag_in_msg = "at_" in msg_l
        has_tag_in_note = bool(re.search(r'[A-Za-z0-9]', note_u))
        if has_tag_in_msg or has_tag_in_note:
            return False
        return True # Discard as Ghost
        
    # Exit Exemption: For non-Trading Evaluator fills, exits are almost always legitimate.
    if not is_open:
        return False
        
    # General Rule: All other fills require an Order Note (Tag 0x82) or strategy in message.
    if re.search(r'[A-Za-z0-9]', note_u) or "at_" in msg_l:
        return False
        
    return True # Discard as Ghost


def _scan_position_fill_order(file_path: str) -> List[str]:
    """
    Scan binary for 'Updated Internal Position ... Fill of InternalOrderID: X' (tag 104).
    Returns list of fill InternalOrderIDs in the order they appear (SC's exact execution order).
    Used for exact pairing: process fills in this order so FIFO matches SC.
    """
    out = []
    try:
        with open(file_path, "rb") as bf:
            d = bf.read(50 * 1024 * 1024)
    except Exception:
        return out
    n = len(d)
    pos = 0
    while pos + 8 <= n:
        try:
            tag = struct.unpack('<I', d[pos:pos+4])[0]
            length = struct.unpack('<I', d[pos+4:pos+8])[0]
            val_start = pos + 8
            val_end = val_start + length
            if val_end > n or length > 65536:
                pos = val_end if val_end <= n else pos + 8
                continue
            if tag == 104 or tag == 0x68:
                raw = d[val_start:val_end]
                s = raw.decode("utf-8", errors="ignore").lower()
                if "updated internal position" in s and "fill of internalorderid:" in s:
                    m = re.search(r"fill of internalorderid:\s*([0-9]+)", s)
                    if m:
                        oid = m.group(1).strip()
                        if oid:
                            out.append(oid)
            pos = val_end
        except Exception:
            pos += 8
    return out


def _parse_file_nitro(file_path: str, acc_filter: List[str] = None, symbol_hint: str = None) -> tuple[List[Dict], List[Dict]]:
    """CANARY_VERSION: 2026-02-26_TAG_126_FIX_V1"""
    with open("import_debug.log", "a") as fld:
        fld.write(f"DEBUG: Running _parse_file_nitro on {file_path} with Adaptive Ghost logic...\n")
    raw_candidates = [] # Buffer for all potential fills in this file
    fills = []
    ghosts = [] 
    seen_keys = set()
    try:
        fn = os.path.basename(file_path).upper()
        if not os.path.exists(file_path):
            return [], []
            
        if os.path.getsize(file_path) == 0: 
            return [], []
        
        with open(file_path, "rb") as bf:
            # Limit read to 200MB per file to prevent RAM blowout in parallel
            d = bf.read(200 * 1024 * 1024) 

        pts = fn.split('.')
        acc = re.sub(r'_UTC$', '', pts[-2] if len(pts) > 1 else fn)
        acc_u = acc.upper()
        
        # Filter by account if acc_filter is provided
        if acc_filter and acc_u not in [a.upper() for a in acc_filter]:
            return [], []

        # Priority 1: Use provided target symbol as the primary context if available
        # The acc_filter parameter is now used for filtering accounts, not symbols.
        # The symbol inference logic below will determine the symbol.
        sh = "Unknown" 
        filename_symbol_inferred = False
        
        # Priority 2: Refine from filename if possible
        for s in SYMBOL_METADATA.keys():
            if re.search(rf"[._]{s}[.\-_]", fn) or fn.startswith(f"{s}-") or acc.startswith(f"{s}_"):
                sh = s
                filename_symbol_inferred = True
                break
        
        # Priority 3: Fallback to symbol_hint if provided and inference failed
        if sh == "Unknown" and symbol_hint:
            sh = symbol_hint.upper()
        
        # Root Cause Fix: Extract Date from Filename to Lock Timestamp Window
        file_date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fn)
        min_valid_ts, max_valid_ts = 1600000000, 2000000000
        f_dt = None # Initialize f_dt
        
        if file_date_match:
            try:
                f_dt = datetime.datetime.strptime(file_date_match.group(1), "%Y-%m-%d")
            except: pass

        offset = 0
        file_len = len(d)
        
        # High-Performance TLV Nitro Grouping Loop
        # Strategy: Group multiple records with identical timestamps into a single logical fill.
        # This handles SC's multi-record reporting (Modify, Fill, Signal) for the same event.
        pending_fill = None
        current_ts_val = 0
        current_ts_str = None
        
        # Temp state for current record (Reset on Tag 102/0x66)
        current_note = ""
        current_msg = ""
        current_tag107 = ""
        current_side_hint = None
        current_oid = None  # OrderID/ServiceOrderID for current record (used to mark canceled orders)
        current_internal_oid = None
        canceled_order_ids = set()  # Order IDs that were "Internally marking as canceled" (rolled-back fills)
        current_record_is_cancel = False  # True if this record's message says order was canceled (Tag 104 may come before Tag 100)
        
        # Default fallback is the date in the filename (start of UTC day)
        base_time = f_dt.timestamp() if f_dt else datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        
        while offset < file_len - 8:
            try:
                tag, length = struct.unpack('<II', d[offset : offset+8])
                
                # Sync Recovery
                if tag == 0 or tag > 512 or length > 65536: 
                    next_ptr = d.find(b'\x66\x00\x00\x00', offset + 1)
                    if next_ptr == -1: break
                    offset = next_ptr
                    continue

                val_start = offset + 8
                val_end = val_start + length
                if val_end > file_len: break
                
                if tag == 102 or tag == 0x66: # Time: Start of a new record
                    new_dt = _parse_tag66_timestamp(d[val_start:val_end])
                    new_ts_val = new_dt.timestamp() if new_dt else 0
                    
                    # FLUSH GROUP if timestamp changes
                    if pending_fill and new_ts_val != current_ts_val:
                        pf = pending_fill
                        # Skip Order-type records: TAL shows 03:05/03:23/03:43 as Orders not Fills (plain "Trade simulation fill" + Limit/Stop)
                        # Real Fills either have "Trading Evaluator (Filled)..." (with note) or plain msg + Market. Ghost (09:05:56) has no note → dropped later.
                        ot = (pf.get("order_type_tag107") or "").lower()
                        msgtxt_l = (pf.get("msgtxt") or "").lower()
                        if pf.get("side") not in ("BUY", "SELL"):
                            pending_fill = None
                        elif pf.get("status_code") not in (None, 8):
                            pending_fill = None
                        elif ("stop" in ot or "limit" in ot) and "trading evaluator" not in msgtxt_l:
                            pending_fill = None  # plain queue/order update records (not TAL Fills)
                        elif ("stop" in ot or "limit" in ot) and not pf.get("has_fill_price_tag"):
                            pending_fill = None  # keep stop/limit only when execution tags are present
                        else:
                            is_v = acc_u.startswith("V_")
                            if not is_v or pf.get('confirmed'):
                                pf["_record_index"] = len(raw_candidates)
                                raw_candidates.append(pf)
                            pending_fill = None

                    if new_dt:
                        current_ts_val, current_ts_str = new_ts_val, new_dt.isoformat()
                    
                    # IDENTITY SHIELD: Reset EVERY record's transient data.
                    # Fills MUST carry their own Tag 0x82 Note to be valid.
                    # This prevents ghosts from inheriting notes from real trades.
                    current_msg = ""; current_tag107 = ""; current_note = ""; current_side_hint = None; current_oid = None; current_internal_oid = None; current_record_is_cancel = False
                
                elif tag == 0x82: # 130: Order Note
                    val = d[val_start:val_end].decode(errors='ignore').strip()
                    if val:
                        current_note = (current_note + " " + val).strip()
                        if pending_fill: pending_fill['note'] = (pending_fill.get('note','') + " " + val).strip()

                elif tag == 107: # Tag 107: Order Type / Internal Info (e.g. "Market", "Limit", "Stop Limit")
                    val = d[val_start:val_end].decode(errors='ignore').strip()
                    if val:
                        current_tag107 = val
                        if pending_fill:
                            pending_fill["order_type_tag107"] = val
                    # DO NOT use as note.

                elif tag == 0x67: # 103: Symbol
                    tsym = d[val_start:val_end].decode(errors='ignore').strip('\x00').strip()
                    if tsym: 
                        sh, filename_symbol_inferred = tsym, True
                        if pending_fill: pending_fill['symbol'] = tsym
                
                elif tag == 100 or tag == 124: # OrderID / ServiceOrderID
                    oid = d[val_start:val_end].decode(errors='ignore').strip()
                    if oid:
                        current_oid = oid
                        if pending_fill: pending_fill['order_id'] = oid
                        if current_record_is_cancel:
                            canceled_order_ids.add(oid)

                elif tag == 101 and pending_fill:  # record code (observed duplicates: 3 vs 4)
                    try:
                        if length == 4:
                            pending_fill["record_code"] = int(struct.unpack('<i', d[val_start:val_start+4])[0])
                    except Exception:
                        pass

                elif tag == 105:  # InternalOrderID (int64 in observed records)
                    try:
                        if length == 8:
                            oid105 = str(int(struct.unpack('<q', d[val_start:val_start+8])[0]))
                            current_internal_oid = oid105
                            if pending_fill:
                                pending_fill["internal_order_id"] = oid105
                    except Exception:
                        pass

                elif tag == 139 and pending_fill:  # observed close-link/order-link field
                    try:
                        v139 = d[val_start:val_end].decode(errors='ignore').strip()
                        if v139:
                            pending_fill["tag139"] = v139
                            # Common format observed: "<id>.<suffix>".
                            # We keep the leading numeric id as a parent candidate.
                            m139 = re.match(r"^(\d+)", v139)
                            if m139:
                                pending_fill["parent_order_id"] = m139.group(1)
                    except Exception:
                        pass

                elif tag == 137 and pending_fill:  # observed service-order-like field
                    try:
                        v137 = d[val_start:val_end].decode(errors='ignore').strip()
                        if v137:
                            pending_fill["service_order_id"] = v137
                    except Exception:
                        pass

                elif tag == 109:  # Buy/Sell code (1=BUY, 2=SELL)
                    try:
                        code = d[val_start]
                        mapped = "BUY" if code == 1 else ("SELL" if code == 2 else None)
                        if mapped:
                            current_side_hint = mapped
                            if pending_fill:
                                pending_fill["side"] = mapped
                    except Exception:
                        pass

                elif tag == 112 and pending_fill:  # Status code (8 observed for filled)
                    try:
                        pending_fill["status_code"] = int(d[val_start])
                    except Exception:
                        pass

                elif tag == 120 and pending_fill:  # Open/Close code (observed: 1=OPEN, 2=CLOSE)
                    try:
                        oc_code = int(d[val_start])
                        pending_fill["open_close"] = "OPEN" if oc_code == 1 else ("CLOSE" if oc_code == 2 else "")
                        pending_fill["open_close_code"] = oc_code
                    except Exception:
                        pass

                elif tag == 113 and pending_fill:  # FillPrice
                    try:
                        if length == 8:
                            p113 = float(struct.unpack('<d', d[val_start:val_start+8])[0])
                            if 0 < p113 < 500000:
                                pending_fill["price"] = p113
                                pending_fill["has_fill_price_tag"] = True
                    except Exception:
                        pass

                elif tag == 114 and pending_fill:  # FilledQuantity
                    try:
                        if length == 8:
                            q114 = int(float(struct.unpack('<d', d[val_start:val_start+8])[0]))
                            if 0 < q114 < 500:
                                pending_fill["quantity"] = max(pending_fill.get("quantity", 0), q114)
                    except Exception:
                        pass

                elif tag == 125 and pending_fill:  # Position quantity after this fill
                    try:
                        if length == 8:
                            pos_after = int(float(struct.unpack('<d', d[val_start:val_start+8])[0]))
                            pending_fill["position_after"] = pos_after
                    except Exception:
                        pass

                elif tag == 160 and pending_fill:  # TransDateTime-like timestamp
                    try:
                        t160 = _parse_tag66_timestamp(d[val_start:val_end])
                        if t160:
                            pending_fill["trans_timestamp"] = t160.isoformat()
                            pending_fill["trans_ts_val"] = t160.timestamp()
                    except Exception:
                        pass

                    
                elif tag == 0x6b: # Tag 107 decimal - ALREADY HANDLED ABOVE
                    pass
                    side = None
                    if any(x in st for x in ["BUY", "LONG"]): side = "BUY"
                    pass

                elif tag == 104 or tag == 0x68: # Message String
                    s = d[val_start : val_end].decode(errors='ignore')
                    current_msg = s
                    s_lower = s.lower()
                    pm = None

                    if "sellentry" in s_lower or "sell entry" in s_lower:
                        current_side_hint = "SELL"
                    elif "buyentry" in s_lower or "buy entry" in s_lower:
                        current_side_hint = "BUY"
                    
                    if pending_fill:
                        pending_fill['msgtxt'] = (pending_fill.get('msgtxt','') + " " + s).strip()
                        if "filled" in s_lower or "simulation fill" in s_lower:
                            pending_fill['confirmed'] = True

                    # Track order IDs that were later canceled (rolled-back simulated fills at 03:05/03:23/03:43)
                    if any(x in s_lower for x in [
                        "internally marking as canceled", "no order update from server",
                        "marking as canceled", "order update from server", "internally marking"
                    ]):
                        current_record_is_cancel = True
                        if current_oid:
                            canceled_order_ids.add(current_oid)

                    # Strong side/qty signal from position update line:
                    # "Updated Internal Position Quantity to -3. Previous: 0. Fill of InternalOrderID: 20091769"
                    pos_upd = re.search(
                        r"updated internal position quantity to\s*(-?\d+)\.\s*previous:\s*(-?\d+)\.\s*fill of internalorderid:\s*([0-9.]+)",
                        s_lower,
                    )
                    if pos_upd and pending_fill:
                        try:
                            new_pos = int(pos_upd.group(1))
                            prev_pos = int(pos_upd.group(2))
                            upd_oid = pos_upd.group(3).strip()
                            delta = new_pos - prev_pos
                            if delta != 0:
                                inferred_side = "BUY" if delta > 0 else "SELL"
                                pending_fill["side"] = inferred_side
                                pending_fill["quantity"] = max(pending_fill.get("quantity", 0), abs(delta))
                            if upd_oid:
                                pending_fill["order_id"] = upd_oid
                        except Exception:
                            pass

                    # Filter out position synchronization and re-stated fills (InternalOrderID/Service).
                    # Do NOT include "trading evaluator" here: "Trading Evaluator (Filled). Info: Trade simulation fill" is a real fill (e.g. 04:18 exit). Ghost (09:05:56) is dropped later by no-note filter.
                    is_position_sync = any(x in s_lower for x in [
                        "updated internal position", 
                        "updated service position", 
                        "updated position quantity",
                        "synchronized internal position",
                        "synchronized service position",
                        "internalorderid",
                        "internal order id"
                    ])
                    
                    if ("trade simulation fill" in s_lower or "fill: " in s_lower or "(filled)" in s_lower) and not is_position_sync:
                        # Ensure we have a symbol/account for this record before creating a trade candidate
                        if sh and acc:
                            pm = re.search(r"(?:fillprice|price)[:\s]*([\d]+\.?[\d]*)", s_lower)
                            try:
                                    p_val = float(pm.group(1).rstrip('.')) if pm else None
                                    side = None
                                    if any(x in s_lower for x in ["buy", "bought", "long"]): side = "BUY"
                                    elif any(x in s_lower for x in ["sell", "sold", "short"]): side = "SELL"
                                    if not side and current_side_hint in ("BUY", "SELL"):
                                        side = current_side_hint
                                    
                                    # New: Buy Sell: N code (1=BUY, 2=SELL)
                                    bsm = re.search(r"buy\s*sell\s*:\s*(\d)", s_lower)
                                    if bsm: side = "BUY" if bsm.group(1) == "1" else "SELL"
                                    
                                    bm = re.search(r"bid[:\s]*([\d]+\.?[\d]*)", s_lower)
                                    am = re.search(r"ask[:\s]*([\d]+\.?[\d]*)", s_lower)
                                    lm = re.search(r"last[:\s]*([\d]+\.?[\d]*)", s_lower)
                                    bid = ask = last = None
                                    try:
                                        if bm: bid = float(bm.group(1).rstrip('.'))
                                        if am: ask = float(am.group(1).rstrip('.'))
                                        if lm: last = float(lm.group(1).rstrip('.'))
                                    except Exception:
                                        bid = ask = last = None

                                    # If explicit fillprice/price is missing, derive from quote context.
                                    if pm is None:
                                        if side == "BUY" and ask is not None:
                                            p_val = ask
                                        elif side == "SELL" and bid is not None:
                                            p_val = bid
                                        elif last is not None:
                                            p_val = last
                                        elif ask is not None:
                                            p_val = ask
                                        elif bid is not None:
                                            p_val = bid
                                        else:
                                            continue
                                    
                                    qty = 1
                                    qm = re.search(r"(?:qty|quantity|size|fill qty|q:|vol)\s*:?\s*(\d+)", s_lower)
                                    if qm: qty = int(qm.group(1))
                                    
                                    asym = sh
                                    tm = re.search(r'\b([A-Z]{1,8}[FGHJKMNQUVXZ]\d{1,2})\b', s.upper())
                                    if tm: asym = tm.group(1)

                                    if not pending_fill:
                                        pending_fill = {
                                            "account_name": acc, "symbol": asym, "price": p_val, "side": side, 
                                            "quantity": qty, "timestamp": current_ts_str, "ts_val": current_ts_val,
                                            "order_id": current_oid, "internal_order_id": current_internal_oid,
                                            "note": current_note, "msgtxt": s, "confirmed": True,
                                            "file_path": fn, "bid": bid, "ask": ask, "last": last
                                        }
                                    else:
                                        pending_fill['price'] = p_val
                                        if side: pending_fill['side'] = side
                                        pending_fill['confirmed'] = True
                                        if bid is not None: pending_fill['bid'] = bid
                                        if ask is not None: pending_fill['ask'] = ask
                                        if last is not None: pending_fill['last'] = last
                                        if qty > pending_fill['quantity']: pending_fill['quantity'] = qty

                                    # If side is known and we have bid/ask, force price to the side-consistent level.
                                    if pending_fill and pending_fill.get("side") in ("BUY", "SELL"):
                                        pf_side = pending_fill["side"]
                                        pf_bid = pending_fill.get("bid")
                                        pf_ask = pending_fill.get("ask")
                                        if pf_side == "BUY" and pf_ask is not None:
                                            pending_fill["price"] = pf_ask
                                        elif pf_side == "SELL" and pf_bid is not None:
                                            pending_fill["price"] = pf_bid
                            except:
                                pass
                    
                elif tag == 108 and pending_fill:
                    try:
                        if length == 8:
                            v = int(struct.unpack('<d', d[val_start:val_start+8])[0])
                            if 0 < v < 500: pending_fill['quantity'] = max(pending_fill.get('quantity', 0), v)
                    except: pass

                if pending_fill:
                    if tag not in pending_fill.get('tags_trace', []):
                        pending_fill.setdefault('tags_trace', []).append(tag)
                
                offset = val_end
            except: break
 # Exit loop on parsing error to prevent infinite loop
        
        # Final flush of any pending fill after the loop finishes
        if pending_fill:
            pf = pending_fill
            ot = (pf.get("order_type_tag107") or "").lower()
            msgtxt_l = (pf.get("msgtxt") or "").lower()
            if pf.get("side") not in ("BUY", "SELL"):
                pass
            elif pf.get("status_code") not in (None, 8):
                pass
            elif ("stop" in ot or "limit" in ot) and "trading evaluator" not in msgtxt_l:
                pass  # plain queue/order update records (not TAL Fills)
            elif ("stop" in ot or "limit" in ot) and not pf.get("has_fill_price_tag"):
                pass  # keep stop/limit only when execution tags are present
            else:
                is_v = acc_u.startswith("V_")
                if not is_v or pf.get('confirmed'):
                    pf["_record_index"] = len(raw_candidates)
                    raw_candidates.append(pf)

        # Drop fills whose order was later canceled (rolled-back simulated fills at 03:05/03:23/03:43)
        raw_candidates = [c for c in raw_candidates if c.get("order_id") not in canceled_order_ids]

        # --- ADAPTIVE GHOST FILTERING ---
        total_c = len(raw_candidates)
        with_notes = sum(1 for c in raw_candidates if c.get('note', '').strip())
        note_rate = (with_notes / total_c) if total_c > 0 else 1.0
        
        # Adaptive Threshold: If <25% of fills have notes, it's a "No-Note Setup"
        # We disable note-based ghost filtering for such files (covers TM_10, TM_2, etc.).
        bypass_ghost_filter = (note_rate < 0.25 and total_c > 5)
        
        if bypass_ghost_filter:
            with open("import_debug.log", "a") as fld:
                fld.write(f"INFO: Low Note-Rate ({note_rate:.1%}) for {acc_u} on {fn}. Bypassing ghost filter.\n")

        # --- PRE-DEDUP ---
        # Note: We now keep ALL potential fills, flagging them as 'suggests_ghost' 
        # instead of dropping them here. Global deduplication in run_import 
        # will then have a chance to find the version of this fill that HAS a note
        # if it was split across files or records.
        seen_raw_keys = set()
        for pf in raw_candidates:
            # Per-file dedup key:
            # - Use a tighter 250ms bucket (not 2s) to avoid collapsing legitimate rapid fills.
            # - Include order_id so distinct fills at same time/price/qty are preserved.
            ts_bucket = round(pf.get('ts_val', 0) * 4) / 4.0
            _raw_key = (
                ts_bucket,
                pf.get('price'),
                pf.get('side'),
                pf.get('quantity'),
                pf.get('account_name'),
                pf.get('order_id'),
            )
            
            # Determine if this specific record looks like a ghost
            # Phase 1: Logic-Based Ghost Detection (Import Shield Rule #2)
            # A fill is only valid if it HAS its own strategy note or is EOD.
            # Exception: Plain "Trade simulation fill" + Market (no "Trading Evaluator" in msg) = TAL Activity Type Fills; note may be in another record.
            if not bypass_ghost_filter:
                # Add specific debug trace to see what the ghost filter sees for 04:05
                debug_trace_04_05 = False
                # Dec 18 04:05 UTC is 1766030700 ts_val
                if pf.get('ts_val', 0) > 1766030650 and pf.get('ts_val', 0) < 1766030750:
                    debug_trace_04_05 = True
                    with open("import_debug.log", "a") as fld:
                        fld.write(f"\n[GHOST FILTER EVAL] 04:05 RECORD FOUND: {current_ts_str} | note='{pf.get('note', '')}' | msg='{pf.get('msgtxt', '')}' | side={pf.get('side', '')} | qty={pf.get('quantity', '')} | ts_val={pf.get('ts_val', 0)}\n")
            
                ot = (pf.get("order_type_tag107") or "").lower()
                msgtxt_l = (pf.get("msgtxt") or "").lower()
                
                # Refine is_open detection for ghost filter
                # Tag 124 is explicit, but we also check side/qty vs previous position if available.
                oc_tag = (pf.get('open_close') or '').upper()
                is_open = True 
                if oc_tag == 'CLOSE':
                    is_open = False
                elif "trading evaluator" in msgtxt_l and pf.get('quantity') == 1:
                    # Heuristic: 1-lot Trading Evaluator fills are often stop-exits
                    # if they don't have strategy tags, we should be careful.
                    # But if it's the 19:17 style, we want to allow it.
                    # We'll rely on _is_ghost_fill's is_open check.
                    pass

                if "trading evaluator" in msgtxt_l:
                     pf['suggests_ghost'] = _is_ghost_fill(pf['account_name'], pf.get('note',''), pf['timestamp'], pf.get('msgtxt',''), is_open=is_open, qty=pf.get('quantity', 0))
                elif "market" in ot and "trading evaluator" not in msgtxt_l:
                    pf['suggests_ghost'] = False
                else:
                    pf['suggests_ghost'] = _is_ghost_fill(pf['account_name'], pf.get('note',''), pf['timestamp'], pf.get('msgtxt',''), is_open=is_open, qty=pf.get('quantity', 0))

            
            if _raw_key not in seen_raw_keys:
                fills.append(pf)
                seen_raw_keys.add(_raw_key)
            else:
                # Duplicate in same file: prefer the latest representation (final post-fill state),
                # and preserve richer metadata.
                for existing in fills:
                    # Find the existing fill in the same dedup bucket
                    if (round(existing.get('ts_val', 0) * 4) / 4.0 == _raw_key[0] and 
                        existing['price'] == _raw_key[1] and 
                        existing['side'] == _raw_key[2] and 
                        existing['quantity'] == _raw_key[3] and
                        existing.get('order_id') == _raw_key[5]):
                        # Keep latest ts snapshot in this dedup group.
                        if (pf.get('ts_val') or 0) >= (existing.get('ts_val') or 0):
                            for k in ("timestamp", "ts_val", "price", "side", "quantity", "order_id", "msgtxt"):
                                if pf.get(k) not in (None, ""):
                                    existing[k] = pf.get(k)
                        if not existing.get('note') and pf.get('note'):
                            existing['note'] = pf['note']
                        existing['suggests_ghost'] = pf.get('suggests_ghost', existing.get('suggests_ghost'))
                        # Merge richer metadata from alternate duplicate representation
                        for k in ("open_close", "open_close_code", "status_code", "internal_order_id", "position_after", "has_fill_price_tag"):
                            if existing.get(k) in (None, "", 0, False) and pf.get(k) not in (None, "", 0, False):
                                existing[k] = pf.get(k)
                        break
        
        return fills, [] # ghosts list is now empty as filtering is deferred
        # The original code had a target_sym check here, which is removed as acc_filter is now the second arg.
        # if sh == "Unknown" and target_sym:
        #     sh = target_sym.upper()
        #     filename_symbol_inferred = True

        with open("import_debug.log", "a") as fld:
            fld.write(f"FILE: {fn} | ACC: {acc} | SYMBOL: {sh} | FILLS: {len(fills)}\n")

    except Exception as e:
        with open("import_debug.log", "a") as fld:
            fld.write(f"ERROR: {os.path.basename(file_path)} -> {str(e)}\n")
            
    return fills, ghosts

class BinaryLogParser:
    def __init__(self, db_path=None):
        if db_path is None:
            from pathlib import Path
            self.db_path = str(Path(__file__).parent.parent.parent / 'trading_platform.db')
        else:
            self.db_path = db_path
        self.running = False
        self.stats = {
            'processed': 0, 'found': 0, 'dropped_long_duration': 0,
            'dropped_outliers': 0, 'dropped_eod_1700': 0, 'dropped_pct': 0,
            'unpaired_fills': 0, 'breakdown': {}, 'canary': 'RELOADED_FEBRUARY_2026'
        }
        self.message = "Idle"
        self.progress = 0
        self.finish_time = None
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
                day_of_week INTEGER,
                trip_id TEXT
            )
        """)
        # Ensure trip_id exists for older DBs
        try:
            c.execute("ALTER TABLE processed_trades ADD COLUMN trip_id TEXT")
        except: pass
        c.execute("""
            CREATE TABLE IF NOT EXISTS pending_fills (
                account_name TEXT,
                symbol TEXT,
                side TEXT,
                entry_time TEXT,
                price REAL,
                quantity INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_proc_trades_acc_sym ON processed_trades(account_name, symbol)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_fills_acc_sym ON pending_fills(account_name, symbol)")
        conn.commit()
        conn.close()

    def stop(self):
        self._stop_event = True
        self.message = "Stopping..."

    def _find_all_fills(self, folders: List[str], acc_filter: List[str] = None, days_lookback: int = 14) -> tuple[List[Dict], List[Dict]]:
        all_fills = []
        all_ghosts = []
        folders = [f for f in folders if os.path.isdir(f)]
        if not folders: return [], []
        
        file_list = []
        for folder in folders:
            # We look for TradeActivityLog files
            all_files = glob.glob(os.path.join(folder, "TradeActivityLog_*.data"))
            for fp in all_files:
                # Filter by days_lookback if provided
                if days_lookback is not None:
                   try:
                       m = re.search(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC', fp)
                       if m:
                           f_date = datetime.datetime.strptime(m.group(1), "%Y-%m-%d")
                           if (datetime.datetime.now() - f_date).days > days_lookback:
                               continue
                   except: pass
                file_list.append(fp)
        
        # Parallel parsing
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            future_to_file = {executor.submit(_parse_file_nitro, fp, acc_filter): fp for fp in file_list}
            for future in concurrent.futures.as_completed(future_to_file):
                fills, ghosts = future.result()
                all_fills.extend(fills)
                all_ghosts.extend(ghosts)
        
        # GLOBAL DEDUPLICATION across all files (Crucial for UTC overlap)
        seen_global_keys = set()
        global_deduped = []
        # Use account and symbol in the key as well to be safe
        for fill in all_fills:
            # 2-second bucket is safe for catching SC double-reports (usually ~460ms apart)
            # while distinguishing truly different trade events.
            gkey = (
                round(fill.get('ts_val', 0) / 2) * 2,
                fill.get('price'),
                fill.get('side'),
                fill.get('quantity'),
                fill.get('account_name'),
                fill.get('symbol')
            )
            if gkey not in seen_global_keys:
                global_deduped.append(fill)
                seen_global_keys.add(gkey)
        
        if len(global_deduped) < len(all_fills):
            with open("import_debug.log", "a") as fld:
                fld.write(f"INFO: Global Dedup removed {len(all_fills)-len(global_deduped)} overlapping fill(s) across files.\n")
        
        all_fills = global_deduped
        all_fills.sort(key=lambda x: (x['timestamp'], x.get('offset', 0)))
        return all_fills, all_ghosts

    async def run_import(self, paths: List[str], filter_symbol: Optional[str] = None, account_filter: Optional[List[str]] = None, days_lookback: Optional[int] = None, defer_ghost_removal: bool = False):
        self.running = True
        self._stop_event = False
        self.stats = {
            'processed': 0, 'found': 0, 
            'dropped_long_duration': 0, 'dropped_outliers': 0, 
            'dropped_eod_1700': 0, 'dropped_ghost_fills': 0,
            'dropped_drift': 0, 'dropped_pct': 0,
            'unpaired_fills': 0, 'breakdown': {}
        }
        self.progress = 0
        self.finish_time = None # Reset finish time at start of new run
        
        try:
            files_to_process = []
            cutoff_time = None
            if days_lookback:
                cutoff_time = (datetime.datetime.now() - datetime.timedelta(days=days_lookback)).timestamp()
                print(f"DEBUG: run_import days_lookback={days_lookback}, cutoff_time={cutoff_time}")

            for path in paths:
                if self._stop_event: break
                cp = os.path.normpath(path)
                print(f"DEBUG: Scanning path: {cp}")
                if os.path.exists(cp):
                    all_data_files = []
                    for ext in ["*.data", "*.DATA", "*.txt", "*.TXT", "*.log", "*.LOG"]:
                        all_data_files.extend(glob.glob(os.path.join(cp, ext)))
                    all_data_files = list(set(all_data_files))
                    
                    # Enhanced Date Filtering: Use filename date as primary, mtime as secondary
                    filtered_files = []
                    cutoff_date_str = None
                    if days_lookback:
                        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_lookback)).date()
                        cutoff_date_str = cutoff_date.isoformat()
                        print(f"DEBUG: cutoff_date_str={cutoff_date_str}")
                    
                    for f in all_data_files:
                        fn = os.path.basename(f)
                        if "TradeActivityLog" not in fn: continue
                        
                        # Case 1: Filename contains date (e.g. 2024-06-02)
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', fn)
                        if date_match and cutoff_date_str:
                            if date_match.group(1) < cutoff_date_str:
                                continue
                        
                        # Case 2: No date in filename or no lookback, check mtime
                        if cutoff_time and os.path.getmtime(f) < cutoff_time:
                            continue
                            
                        filtered_files.append(f)
                    files_to_process.extend(filtered_files)
            
            files_to_process = sorted(list(files_to_process))
            
            if account_filter:
                if isinstance(account_filter, str):
                    acc_set = {account_filter.upper()}
                else:
                    acc_set = {str(a).upper() for a in account_filter}
                files_to_process = [f for f in files_to_process if any(acc in os.path.basename(f).upper() for acc in acc_set)]
            
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
            all_ghosts_collected = [] # New list to collect all ghosts
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
                    # Pass account_filter and filter_symbol (as hint) to _parse_file_nitro
                    tasks = [loop.run_in_executor(executor, partial(_parse_file_nitro, fp, account_filter, filter_symbol)) for fp in batch]
                    
                    for f_task in await asyncio.gather(*tasks):
                        if not isinstance(f_task, (list, tuple)) or len(f_task) < 2:
                            continue
                        res_fills, res_ghosts = f_task
                        
                        if isinstance(res_fills, list):
                            for f in res_fills:
                                if not isinstance(f, dict): continue
                                # Safety catch for None ts_val
                                ts_val = f.get('ts_val', 0)
                                if ts_val is None: ts_val = 0
                                
                                # RULE 4: Millisecond-Precise Deduplication
                                # Deduplication key is (Timestamp rounded to 500ms, Price, Side, Quantity...).
                                # Instance-Aware: Only dedup if from the SAME instance path (parent folder).
                                ts_bucket_500ms = round(ts_val * 2) / 2.0
                                msg_hash = hash(f.get('msgtxt', ''))
                                instance_path = os.path.dirname(f.get('file_path', 'default')) 
                                key = (instance_path, f.get('account_name'), f.get('symbol'), f.get('side'), f.get('price'), f.get('quantity'), ts_bucket_500ms, msg_hash)
                                
                                if key not in all_unique_fills:
                                    all_unique_fills[key] = f
                                else:
                                    # If identical message/time/price/instance, deduplicate.
                                    # Prefer the version with a note if available.
                                    if all_unique_fills[key].get('suggests_ghost') and not f.get('suggests_ghost'):
                                        all_unique_fills[key] = f
                        
                    self.stats["processed"] = min(total_files, i + batch_size)
                    await asyncio.sleep(0.01)

            # Midnight Sync Protection Audit (DEPRECATED: Using Keyword Filtering instead)
            # We now rely on 'trading evaluator' and 'sync' keywords in _parse_file_nitro.
            pass

            # --- POST-DEDUP GHOST FILTERING ---
            # Ghost = one leg only. We remove only the ghost leg; the entry stays and the next
            # real close pairs with it (re-match). When defer_ghost_removal=False we drop ghost
            # fills here so they never enter pairing. When defer_ghost_removal=True we pass all
            # fills; _pairs_to_trades skips ghost close legs (does not consume from queue).
            all_fills = sorted(list(all_unique_fills.values()), key=lambda x: x.get('ts_val', 0))
            
            final_fills = []
            for f in all_fills:
                if f.get('suggests_ghost'):
                    if not defer_ghost_removal:
                        all_ghosts_collected.append({
                            "account": f['account_name'], "timestamp": f['timestamp'],
                            "symbol": f['symbol'], "side": f['side'],
                            "price": f['price'], "quantity": f['quantity'], "note": f.get('note','')
                        })
                        continue  # drop ghost fills before pairing
                final_fills.append(f)
            
            all_fills = final_fills
            self.stats["found"] = len(all_fills)
            self.stats["dropped_ghost_fills"] = 0 if defer_ghost_removal else len(all_ghosts_collected)

            if not all_fills and not all_ghosts_collected:
                self.message = f"Done. No valid trades or ghosts found in {total_files} files."
                self.running = False
                return
            
            deduped_fills = all_fills
            
            self.message = "FIFO Reconstruction..."
            # _pairs_to_trades now receives the deduped_fills
            trades, unpaired, position_warnings = self._pairs_to_trades(deduped_fills, persist_state=True)
            
            # --- POST-PAIR GHOST REMOVAL (defer_ghost_removal mode) ---
            # Ghost close legs are already skipped in _pairs_to_trades (no consume from queue).
            # Here we only remove trades where the entry was a ghost (rare).
            if defer_ghost_removal and trades:
                ghost_trades = [t for t in trades if t.get("entry_suggests_ghost") or t.get("exit_suggests_ghost")]
                trades = [t for t in trades if not (t.get("entry_suggests_ghost") or t.get("exit_suggests_ghost"))]
                # Strip ghost flags before save (not needed in DB)
                for t in trades:
                    t.pop("entry_suggests_ghost", None)
                    t.pop("exit_suggests_ghost", None)
                ghost_trade_count = len(ghost_trades)
                self.stats["dropped_ghost_fills"] = ghost_trade_count
                if ghost_trade_count > 0:
                    for gt in ghost_trades:
                        all_ghosts_collected.append({
                            "account": gt.get("account", ""), "timestamp": gt.get("exit_time", ""),
                            "symbol": gt.get("symbol", ""), "side": gt.get("side", ""),
                            "price": gt.get("exit_price", 0), "quantity": gt.get("quantity", 0),
                            "note": "(ghost trade removed post-pair)"
                        })
            
            if not trades and not unpaired:
                self.message = "No fills found to process."
                self.finish_time = datetime.datetime.now().isoformat()
                self.running = False
                return

            self.message = f"Aggregating split fills for {len(trades)} trades..."
            for t in trades:
                t.pop("entry_suggests_ghost", None)
                t.pop("exit_suggests_ghost", None)
            trades = self._aggregate_trades(trades)
            
            self.message = "Saving to DB..."
            new_count = self._save_trades_to_db(trades)
            
            # Debug Trace: Did we actually save any Feb 17 trades for SIM15?
            sim15_feb17 = [t for t in trades if t['account'].upper() == '3Q_SIM15' and '2026-02-17' in t['entry_time']]
            with open("import_debug.log", "a") as fld:
                fld.write(f"FINAL SAVE CHECK: 3Q_SIM15 Feb 17 trades in list: {len(sim15_feb17)}\n")
            
            self.message = "Applying Shield Rules (Purging Anomalies)..."
            # Restriction: Only purge and report on accounts that were actually found in this import run
            accounts_in_run = list({f['account_name'] for f in deduped_fills})
            breakdown = self.purge_anomalies(account=accounts_in_run, symbol=filter_symbol, purge_overnight=True)
            
            # Aggregate stats across all accounts (counts and PnL for removed trades)
            total_future = sum(b.get("future", {}).get("count", 0) for b in breakdown.values())
            total_long_duration = sum(b.get("long_duration", {}).get("count", 0) for b in breakdown.values())
            total_long_duration_pnl = sum(b.get("long_duration", {}).get("pnl", 0.0) for b in breakdown.values())
            total_outliers = sum(b.get("outliers", {}).get("count", 0) for b in breakdown.values())
            total_eod_1700 = sum(b.get("eod_1700", {}).get("count", 0) for b in breakdown.values())
            total_eod_1700_pnl = sum(b.get("eod_1700", {}).get("pnl", 0.0) for b in breakdown.values())
            total_price_mismatch = sum(b.get("price_mismatch", {}).get("count", 0) for b in breakdown.values())
            
            # PARSING GHOSTS (No Note / Tag 82)
            total_parsing_ghosts = len(all_ghosts_collected) # Use the length of the collected ghosts list
            
            # Position Warnings (open > 3, diagnostic only, NOT blocked)
            total_position_warnings = sum(position_warnings.values())
            
            total_dropped = total_future + total_long_duration + total_outliers + total_eod_1700 + total_price_mismatch + total_parsing_ghosts
            attempted = new_count + total_dropped
            drop_pct = round((total_dropped / attempted * 100), 1) if attempted > 0 else 0
            
            # Final Stats Update (include PnL lost on removed categories for reporting)
            self.stats["found"] = new_count
            self.stats["unpaired_fills"] = unpaired
            self.stats["dropped_long_duration"] = total_long_duration
            self.stats["dropped_long_duration_pnl"] = round(total_long_duration_pnl, 2)
            self.stats["dropped_eod_1700"] = total_eod_1700
            self.stats["dropped_eod_1700_pnl"] = round(total_eod_1700_pnl, 2)
            self.stats["dropped_outliers"] = total_outliers
            self.stats["dropped_ghost_fills"] = total_parsing_ghosts
            self.stats["position_warnings"] = total_position_warnings
            self.stats["dropped_pct"] = drop_pct
            
            # Map parsing ghost counts back into breakdown with correct structure
            # Iterate through all_ghosts_collected to update breakdown
            ghost_counts_by_account = {}
            for ghost_fill in all_ghosts_collected:
                acc_name = ghost_fill.get('account', 'UNKNOWN').upper()
                ghost_counts_by_account[acc_name] = ghost_counts_by_account.get(acc_name, 0) + 1

            for acc, gcnt in ghost_counts_by_account.items():
                if acc not in breakdown:
                    breakdown[acc] = {
                        "future": {"count": 0, "pnl": 0.0, "qty": 0},
                        "long_duration": {"count": 0, "pnl": 0.0, "qty": 0},
                        "outliers": {"count": 0, "pnl": 0.0, "qty": 0},
                        "eod_1700": {"count": 0, "pnl": 0.0, "qty": 0},
                        "price_mismatch": {"count": 0, "pnl": 0.0, "qty": 0},
                        "ghost": {"count": 0, "pnl": 0.0, "qty": 0},
                        "position_warnings": {"count": 0}
                    }
                
                if not isinstance(acc, str) or not isinstance(breakdown.get(acc), dict):
                    continue
                    
                if "ghost" not in breakdown[acc]:
                    breakdown[acc]["ghost"] = {"count": 0, "pnl": 0.0, "qty": 0}
                breakdown[acc]["ghost"]["count"] += gcnt
            
            # Map position warning counts into breakdown for UI visibility
            for acc, pw_count in position_warnings.items():
                if acc and acc in breakdown:
                    if not isinstance(breakdown[acc], dict): continue
                    
                    if "position_warnings" not in breakdown[acc]:
                        breakdown[acc]["position_warnings"] = {"count": 0}
                    breakdown[acc]["position_warnings"]["count"] += pw_count
            
            self.stats["breakdown"] = breakdown
            
            # Human-readable summary: include >24h and EOD removed (count + PnL lost)
            parts = [f"Added: {new_count} | Dropped: {total_dropped} ({drop_pct}%) | Open: {unpaired} fills"]
            if total_long_duration > 0 or total_eod_1700 > 0:
                parts.append("Removed: ")
                if total_long_duration > 0:
                    parts.append(f">24h: {total_long_duration} trades (${total_long_duration_pnl:,.0f} PnL)")
                if total_eod_1700 > 0:
                    if total_long_duration > 0:
                        parts.append(" | ")
                    parts.append(f"EOD(17:00): {total_eod_1700} trades (${total_eod_1700_pnl:,.0f} PnL)")
            self.message = "Import Complete! " + "".join(parts)
            self.finish_time = datetime.datetime.now().isoformat()
            
            with open("import_debug.log", "a") as fld:
                fld.write(f"SUMMARY: Added {new_count}, Dropped {total_dropped} ({drop_pct}%), Unpaired (Open) {unpaired}\n")
                if total_long_duration > 0 or total_eod_1700 > 0:
                    fld.write(f"REMOVED >24h: {total_long_duration} trades, PnL lost: ${total_long_duration_pnl:.2f}\n")
                    fld.write(f"REMOVED EOD(17:00): {total_eod_1700} trades, PnL lost: ${total_eod_1700_pnl:.2f}\n")
                fld.write(f"BREAKDOWN: {str(breakdown)}\n")
            
        except Exception as e:
            import traceback
            err_msg = str(e)
            full_trace = traceback.format_exc()
            self.message = f"Nitro Error: {err_msg}"
            self.finish_time = datetime.datetime.now().isoformat()
            
            with open("import_debug.log", "a") as fld:
                fld.write(f"CRITICAL ERROR: {err_msg}\n{full_trace}\n")
            print(f"CRITICAL ERROR during import: {err_msg}")
            print(full_trace)
        finally:
            self.running = False

    def _pairs_to_trades(self, fills: List[Dict], persist_state: bool = True) -> tuple[List[Dict], int, Dict[str, int]]:
        all_trades = []
        unpaired_count = 0
        position_warnings = {} 
        
        groups = {}
        for f in fills:
            key = (f['account_name'], f['symbol'])
            if key not in groups: groups[key] = []
            groups[key].append(f)
            
        try:
            for (acc, specific_sym), group in groups.items():
                base_sym = _get_base_symbol_standalone(specific_sym)
                meta = SYMBOL_METADATA.get(base_sym, {"multiplier": 1, "comm": 4.20})
                multiplier = meta['multiplier']
                commission_per_leg = meta['comm'] / 2.0
                
                # Sort by absolute sequence
                group.sort(key=lambda x: (x.get('_position_order', 999999), x.get('ts_val', 0), x.get('file_path', ''), x.get('_record_index', 0), x.get('offset', 0)))

                running_position = 0
                open_legs = [] 
                last_session_date = None
                trip_id_counter = 1

                for f in group:
                    # In sequence report mode (include_ghost=True), ghosts are included in fills.
                    # We MUST skip their impact on position and pairing if flagged.
                    is_ghost = f.get('suggests_ghost', False)
                    if is_ghost:
                        continue
                    
                    # RULE 9: Session-Boundary FIFO Reset (17:00 NY)
                    # Every trading day at 17:00 NY, the strategy flattens and the platform resets.
                    # This prevents data contamination (e.g. ghost fills) from one session 
                    # carrying into the next.
                    fill_ts = f.get('timestamp')
                    if fill_ts:
                        try:
                            # Standard format: 2026-02-25T08:16:02.483
                            dt_obj = datetime.datetime.fromisoformat(fill_ts.replace("Z", ""))
                            # Determine the "Trade Session Date" (rolls at 17:00 NY)
                            current_session_date = _session_trade_date_ny(dt_obj)
                            
                            if last_session_date is not None and current_session_date != last_session_date:
                                # Boundary crossed! Flush unpaired legs as 'unpaired' and reset for new session.
                                if open_legs:
                                    unpaired_count += sum(l['qty'] for l in open_legs)
                                    # Log for diagnostics
                                    with open("import_debug.log", "a") as fld:
                                        fld.write(f"INFO: Rule 9 Reset for {acc} {specific_sym} at {fill_ts}. Flushed {len(open_legs)} legs.\n")
                                
                                open_legs = []
                                running_position = 0
                            
                            last_session_date = current_session_date
                        except Exception as e:
                            # If timestamp parsing fails, stay in current state to be safe.
                            pass

                    side = f['side']
                    qty = f['quantity']
                    price = f['price']
                    ts = f['timestamp']

                    # --- Ghost Trade Sequence Resynchronization ---
                    # SC provides 'position_after' (Tag 125) indicating its true internal position.
                    # We can use this to detect "ghost trades" (silently dropped/rolled-back sequences).
                    pos_after = f.get('position_after')
                    if pos_after is not None:
                        # Calculate what SC's position was BEFORE this fill
                        sc_pre_pos = pos_after - qty if side == 'BUY' else pos_after + qty
                        
                        if ts and ts.startswith('2025-12-18T04:18:31'):
                            print(f"[{ts}] SYNC CHECK: sc_pre_pos={sc_pre_pos}, running_position={running_position}")
                            
                        # If SC thinks it was flat before this fill, but we have residual open legs...
                        if sc_pre_pos == 0 and running_position != 0:
                            # This means the current open_legs belong to a "Ghost Trade" sequence
                            # that SC silently wiped out (e.g. the 02:26 3-lot).
                            # We must purge these orphaned legs to resync!
                            for leg in open_legs:
                                if 'fill_ref' in leg:
                                    leg['fill_ref']['suggests_ghost'] = True
                                    leg['fill_ref']['note'] = leg['fill_ref'].get('note', '') + " (GHOST NOISE)"
                            open_legs = []
                            running_position = 0
                            trip_id_counter += 1 # New trip after ghost resync
                            
                    prev_pos = running_position
                    if side == 'BUY':
                        running_position += qty
                    else:
                        running_position -= qty
                    
                    trip_key = f"{acc}_{specific_sym}_{trip_id_counter}"

                    # If this fill increases the magnitude of position, it's an Entry
                    if abs(running_position) > abs(prev_pos):
                        open_legs.append({
                            "qty": qty, "price": price, "time": ts, "side": side, "fill_ref": f
                        })
                    else:
                        # It's an Exit. Match against open_legs (FIFO within position)
                        rem_qty = qty
                        while rem_qty > 0 and open_legs:
                            # Match against first leg with opposite side
                            # (Usually all open_legs have same side)
                            match_idx = -1
                            for i, leg in enumerate(open_legs):
                                if leg['side'] != side:
                                    match_idx = i
                                    break
                            
                            if match_idx == -1:
                                # Direction Flip
                                break
                                
                            leg = open_legs[match_idx]
                            take = min(rem_qty, leg['qty'])
                            
                            pnl = 0
                            if side == 'SELL': # Closing Long
                                pnl = (price - leg['price']) * take * multiplier
                            else: # Closing Short
                                pnl = (leg['price'] - price) * take * multiplier
                                
                            all_trades.append({
                                "account": acc, "symbol": specific_sym,
                                "side": "LONG" if leg['side'] == 'BUY' else "SHORT",
                                "quantity": int(take),
                                "entry_time": leg['time'], "exit_time": ts,
                                "entry_price": leg['price'], "exit_price": price,
                                "profit_loss": round(pnl, 2),
                                "commission": round(take * commission_per_leg * 2, 2),
                                "trip_id": trip_key
                            })
                            
                            leg['qty'] -= take
                            rem_qty -= take
                            if leg['qty'] <= 0:
                                open_legs.pop(match_idx)
                                
                        # End of fill: if we hit zero or crossed zero, increment trip counter
                        passed_zero = (prev_pos > 0 and running_position <= 0) or (prev_pos < 0 and running_position >= 0)
                        if passed_zero and prev_pos != 0:
                            trip_id_counter += 1
                        
                        if rem_qty > 0:
                            # Flipped position. Remainder is new entry phase.
                            open_legs.append({
                                "qty": rem_qty, "price": price, "time": ts, "side": side, "fill_ref": f
                            })
                
                unpaired_count += sum(l['qty'] for l in open_legs)
                if running_position != 0:
                    position_warnings[acc] = position_warnings.get(acc, 0) + 1

        finally:
            pass # DB persistence not used for sequence builder
            
        return all_trades, int(unpaired_count), position_warnings


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
                specific_sym = t['symbol'].upper()
                # RULE 5-Display: Aggregate expirations for UI/Grouping
                base_sym = _get_base_symbol_standalone(specific_sym)
                
                sig = f"{acc_upper}_{specific_sym}_{side}_{t['entry_time']}_{t['exit_time']}_{t['entry_price']}_{t['exit_price']}_{t['quantity']}"
                tid = "T" + hashlib.md5(sig.encode()).hexdigest()[:12]
                c.execute("""
                    INSERT OR REPLACE INTO processed_trades (
                        trade_id, account_name, symbol, entry_time, exit_time, 
                        entry_price, exit_price, quantity, side, 
                        profit_loss, commission, duration_minutes,
                        hour_of_day, day_of_week, trip_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (tid, acc_upper, base_sym, t['entry_time'], t['exit_time'],
                      t['entry_price'], t['exit_price'], t['quantity'], side, 
                      t['profit_loss'], t['commission'], duration, hour, dow, t.get('trip_id')))
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
        
        # Normalize symbol for SQL searching if provided (e.g. NQH26 -> NQ)
        if symbol:
            symbol = _get_base_symbol_standalone(symbol.upper())
        
        # Determine which accounts to process
        if account:
            if isinstance(account, list):
                accounts = account
            else:
                accounts = [account]
        else:
            # If no account specified, default to ONLY accounts that have data in the symbol if provided
            # Or just fall back to all. But we prefer explicit list.
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
            
            # Optimized SQL-based checks for Future and Long Duration
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

            # 2. Long Duration > 24h (SQL) — trades with entry-to-exit span > 1 day
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
                        if _crosses_daily_close_ny(t1, t2):
                            ids_to_drop_eod.append(tid)
                            pnl_eod += (float(pnl) if pnl else 0.0)
                            qty_eod += (int(qty) if qty else 0)
                    except: pass

            # Log deletions for debugging (always log purge summary so >24h / EOD counts are visible)
            if ids_to_drop_future or ids_to_drop_long or ids_to_drop_eod:
                print(f"DEBUG: EXECUTION CONFIRMED - Purging {len(ids_to_drop_eod)} EOD trades for {acc}")
            with open("import_debug.log", "a") as f:
                f.write(f"PURGE {acc}: Future={len(ids_to_drop_future)} (${pnl_future:.2f}) | Long(>24h)={len(ids_to_drop_long)} (${pnl_long:.2f}) | EOD={len(ids_to_drop_eod)} (${pnl_eod:.2f})\n")
                if ids_to_drop_future or ids_to_drop_long or ids_to_drop_eod:
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

    def get_reconciliation_report(self, account_name: str, symbol: Optional[str] = None):
        """
        Generates a daily summary for benchmark comparison.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        where_clause = "WHERE account_name = ? COLLATE NOCASE"
        params = [account_name]
        if symbol:
            where_clause += " AND symbol LIKE ? || '%'"
            params.append(symbol)
            
        c.execute(f"""
            SELECT date(entry_time) as trade_day, 
                   COUNT(*) as trade_count, 
                   SUM(quantity) as total_qty, 
                   SUM(profit_loss) as total_pnl
            FROM processed_trades
            {where_clause}
            GROUP BY trade_day
            ORDER BY trade_day DESC
        """, params)
        
        rows = c.fetchall()
        conn.close()
        
        print(f"\n--- RECONCILIATION REPORT: {account_name} ---")
        print(f"{'Date':<12} | {'Trades':<8} | {'Qty':<8} | {'PnL':<12}")
        print("-" * 50)
        for r in rows:
            print(f"{r[0]:<12} | {r[1]:<8} | {r[2]:<8} | ${r[3]:>10.2f}")
        return rows

importer = BinaryLogParser()
