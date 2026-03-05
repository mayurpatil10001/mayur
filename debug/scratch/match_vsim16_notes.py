import os
import glob
import struct
import re
from datetime import datetime

def scan_vsim16_trades_notes():
    data_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    pattern = os.path.join(data_dir, "*v_sim16*.data")
    files = glob.glob(pattern)
    files += glob.glob(os.path.join(data_dir, "*v_sim16*.DATA"))
    files = sorted(list(set(files)))

    # Simplified FIFO matching logic
    all_fills = []
    
    for fp in files:
        try:
            with open(fp, "rb") as bf:
                d = bf.read()
            
            file_len = len(d)
            offset = 0
            current_ts = ""
            
            while offset < file_len - 8:
                tag, length = struct.unpack('<II', d[offset : offset+8])
                val_start = offset + 8
                val_end = val_start + length
                if val_end > file_len: break
                
                if tag == 0x66:
                    # Time parsing (simplified, just to keep order)
                    pass
                elif tag == 0x68: # 104: Message String
                    s = d[val_start:val_end].decode(errors='ignore').strip()
                    s_lower = s.lower()
                    
                    if ("trade simulation fill" in s_lower or "fill: " in s_lower) and "updated internal position" not in s_lower:
                        # Extract price, side, qty
                        pm = re.search(r"(?:price|at)[:\s]*([\d]+\.?[\d]*)", s_lower)
                        if pm:
                            price = float(pm.group(1).rstrip('.'))
                            side = "BUY" if any(x in s_lower for x in ["buy", "bought", "long"]) else "SELL"
                            
                            qty = 1
                            qm = re.search(r"(?:qty|quantity|size|q:)\s*:?\s*(\d+)", s_lower)
                            if qm: qty = int(qm.group(1))
                            
                            has_note = "AT_NQ_TM" in s
                            all_fills.append({"price": price, "side": side, "qty": qty, "has_note": has_note, "file": os.path.basename(fp)})
                            
                offset = val_end
        except: pass

    # Matching
    buys, sells = [], []
    trades_with_note = 0
    trades_without_note = 0 # Specifically trades where at least one leg is missing the note
    
    for f in all_fills:
        qty = f['qty']
        if f['side'] == 'BUY':
            while qty > 0 and sells:
                m_qty = min(qty, sells[0]['qty'])
                # If either the entry (sell) or exit (buy) is missing a note
                if not f['has_note'] or not sells[0]['has_note']:
                    trades_without_note += 1
                else:
                    trades_with_note += 1
                qty -= m_qty
                sells[0]['qty'] -= m_qty
                if sells[0]['qty'] <= 0: sells.pop(0)
            if qty > 0: buys.append({"qty": qty, "has_note": f['has_note']})
        else: # SELL
            while qty > 0 and buys:
                m_qty = min(qty, buys[0]['qty'])
                if not f['has_note'] or not buys[0]['has_note']:
                    trades_without_note += 1
                else:
                    trades_with_note += 1
                qty -= m_qty
                buys[0]['qty'] -= m_qty
                if buys[0]['qty'] <= 0: buys.pop(0)
            if qty > 0: sells.append({"qty": qty, "has_note": f['has_note']})

    print(f"\n--- V_SIM16 Trades (Matched from Binary) ---")
    print(f"Total Trades Matched: {trades_with_note + trades_without_note}")
    print(f"Trades where all fills HAVE notes: {trades_with_note}")
    print(f"Trades where at least one fill MISSED a note: {trades_without_note}")

if __name__ == "__main__":
    scan_vsim16_trades_notes()
