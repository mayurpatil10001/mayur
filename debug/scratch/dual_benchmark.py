import os
import struct
import re
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

def get_sc_time_v3(value_bytes):
    if len(value_bytes) >= 8:
        try:
            q_val = struct.unpack('<q', value_bytes[:8])[0]
            if 3000000000000000 < q_val < 4500000000000000:
                return datetime.datetime(1899, 12, 30) + datetime.timedelta(microseconds=q_val)
        except: pass
    return None

def extract_fills(path):
    fills = []
    with open(path, "rb") as bf: d = bf.read()
    offset = 0
    current_dt = None
    current_note = ""
    pending = None
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        
        if tag == 0x66:
            if pending:
                pending['note'] = current_note
                fills.append(pending)
                pending = None
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt: current_dt = dt
            current_note = ""
            
        elif tag == 0x82:
            current_note = d[val_start:val_end].decode(errors='ignore').strip()
            if pending: pending['note'] = current_note
            
        elif tag == 0x68:
            s_orig = d[val_start:val_end].decode(errors='ignore')
            s = s_orig.lower()
            if "simulation fill" in s:
                # Logic from corrected_ghost_scan.py
                bm = re.search(r"bid[:\s]*([\d]+\.?[\d]*)", s)
                am = re.search(r"ask[:\s]*([\d]+\.?[\d]*)", s)
                lm = re.search(r"last[:\s]*([\d]+\.?[\d]*)", s)
                
                if bm and am and lm:
                    bid = float(bm.group(1).rstrip('.'))
                    ask = float(am.group(1).rstrip('.'))
                    last = float(lm.group(1).rstrip('.'))
                    side = "BUY" if abs(last - ask) < abs(last - bid) else "SELL"
                    p = last 
                    
                    qty = 1
                    qm = re.search(r"(?:qty|quantity|size|fill qty|q:|vol)\s*:?\s*(\d+)", s)
                    if qm: qty = int(qm.group(1))
                    
                    pending = {
                        "dt": current_dt,
                        "side": side,
                        "qty": qty,
                        "price": p,
                        "msg": s_orig
                    }
        offset = val_end
    if pending:
        pending['note'] = current_note
        fills.append(pending)
    return fills

def match_fifo(fills, multiplier=20):
    buys, sells = [], []
    trades = []
    for f in fills:
        qty = f['qty']
        if f['side'] == 'BUY':
            while qty > 0 and sells:
                s = sells[0]
                m_qty = min(qty, s['qty'])
                trades.append({"pnl": (s['price'] - f['price']) * m_qty * multiplier, "day": f['dt'].date()})
                qty -= m_qty
                s['qty'] -= m_qty
                if s['qty'] <= 0: sells.pop(0)
            if qty > 0: buys.append({"qty": qty, "price": f['price'], "dt": f['dt']})
        else:
            while qty > 0 and buys:
                b = buys[0]
                m_qty = min(qty, b['qty'])
                trades.append({"pnl": (f['price'] - b['price']) * m_qty * multiplier, "day": f['dt'].date()})
                qty -= m_qty
                b['qty'] -= m_qty
                if b['qty'] <= 0: buys.pop(0)
            if qty > 0: sells.append({"qty": qty, "price": f['price'], "dt": f['dt']})
    return trades, buys, sells

def run_dual_benchmark(day_str):
    path = rf"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_{day_str}_UTC.V_sim16.data"
    if not os.path.exists(path):
        print("File not found.")
        return
        
    all_fills = extract_fills(path)
    # Sort by time
    all_fills.sort(key=lambda x: x['dt'])
    
    # 1. RAW (Import everything)
    raw_trades, raw_buys, raw_sells = match_fifo(all_fills)
    raw_pnl = sum(t['pnl'] for t in raw_trades)
    
    # 2. STRATEGY-STRICT (Only AT_NQ_TM or EOD)
    def is_valid(f):
        if 'AT_NQ_TM' in f.get('note', ''): return True
        # EOD logic
        ny = f['dt'].replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        if (ny.hour == 16 and ny.minute >= 57) or (ny.hour == 17 and ny.minute <= 0):
             return True
        return False
        
    strict_fills = [f for f in all_fills if is_valid(f)]
    strict_trades, strict_buys, strict_sells = match_fifo(strict_fills)
    strict_pnl = sum(t['pnl'] for t in strict_trades)
    
    print(f"\n--- DUAL BENCHMARK FOR {day_str} (V_SIM16) ---")
    print(f"{'Metric':<20} | {'RAW (Ghosted)':<15} | {'STRICT (Clean)':<15}")
    print("-" * 60)
    print(f"{'Total Fills':<20} | {len(all_fills):<15} | {len(strict_fills):<15}")
    print(f"{'Completed Trades':<20} | {len(raw_trades):<15} | {len(strict_trades):<15}")
    print(f"{'Realized PnL':<20} | ${raw_pnl:>13.2f} | ${strict_pnl:>13.2f}")
    print(f"{'Open Position':<20} | {sum(b['qty'] for b in raw_buys)-sum(s['qty'] for s in raw_sells):<15} | {sum(b['qty'] for b in strict_buys)-sum(s['qty'] for s in strict_sells):<15}")
    print(f"\nConclusion: Strict filtering removed {len(all_fills)-len(strict_fills)} problematic fills.")
    print(f"Difference in PnL: ${strict_pnl - raw_pnl:.2f}")

if __name__ == "__main__":
    run_dual_benchmark("2025-12-18")
    run_dual_benchmark("2025-12-17")
