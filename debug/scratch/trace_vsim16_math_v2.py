import os
import struct
import re
import datetime

def get_sc_time_v3(value_bytes):
    if len(value_bytes) >= 8:
        try:
            q_val = struct.unpack('<q', value_bytes[:8])[0]
            if 3000000000000000 < q_val < 4500000000000000:
                return datetime.datetime(1899, 12, 30) + datetime.timedelta(microseconds=q_val)
        except: pass
    return None

def trace_vsim16_dec18_pos_math_to_file():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    with open(data_path, "rb") as bf: d = bf.read()
    
    offset = 0
    current_dt = None
    fills = []
    
    while offset < len(d) - 16:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        if tag == 0x66:
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt: current_dt = dt
        elif tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            if ("trade simulation fill" in s.lower() or "fill: " in s.lower()):
                side = "BUY" if any(x in s.lower() for x in ["buy", "bought", "long"]) else "SELL"
                qty = 1
                qm = re.search(r"(?:qty|quantity|size|q:)\s*:?\s*(\d+)", s.lower())
                if qm: qty = int(qm.group(1))
                has_note = "AT_NQ_TM" in s
                fills.append({"dt": current_dt, "side": side, "qty": qty, "has_note": has_note, "msg": s})
        offset = val_end

    with open("math_trace_results.txt", "w") as f_out:
        f_out.write(f"--- V_SIM16 Dec 18 Position Math Tracing ---\n")
        pos = 0
        for f in fills:
            change = f['qty'] if f['side'] == 'BUY' else -f['qty']
            old_pos = pos
            pos += change
            ny_dt = f['dt'] - datetime.timedelta(hours=5) if f['dt'] else datetime.datetime(2000,1,1)
            dt_str = ny_dt.strftime('%H:%M:%S')
            
            if abs(pos) > 6 or not f['has_note']:
                status = "NOTELESS" if not f['has_note'] else "OVERLIMIT"
                f_out.write(f"[{status}] {dt_str} | Side: {f['side']} | Qty: {f['qty']} | POS: {old_pos} -> {pos} | Msg: {f['msg'][:120]}\n")

if __name__ == "__main__":
    trace_vsim16_dec18_pos_math_to_file()
