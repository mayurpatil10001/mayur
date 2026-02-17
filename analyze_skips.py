import re
import os
import struct

def check_parser_skips(fp):
    with open(fp, "rb") as f:
        d = f.read()
    
    offset = 0
    total_104 = 0
    skipped_no_keywords = 0
    skipped_no_prices = 0
    skipped_no_side = 0
    skipped_symbol_mismatch = 0
    skipped_price_sanity = 0
    
    target_sym = "CL"
    
    while offset < len(d) - 12:
        next_marker = d.find(b'\x00\x00\x00', offset + 1)
        if next_marker == -1: break
        offset = next_marker - 1
        tag = d[offset]
        
        if tag == 0x68: # 104
            total_104 += 1
            length = struct.unpack('<I', d[offset+4:offset+8])[0]
            val_bytes = d[offset+8 : offset+8+length]
            s = val_bytes.decode(errors='ignore').lower()
            
            if not any(x in s for x in ["fill", "trade", "bought", "sold", "price"]):
                skipped_no_keywords += 1
                offset += 8 + length
                continue
                
            pm = re.search(r"(?:last|price|fillprice|at)[:\s]*(\d+\.?\d*)", s)
            if not pm:
                skipped_no_prices += 1
                offset += 8 + length
                continue
                
            side = None
            if any(x in s for x in ["buy", "bought", "long"]): side = "BUY"
            elif any(x in s for x in ["sell", "sold", "short"]): side = "SELL"
            
            if not side:
                bm = re.search(r"bid[:\s]*(\d+\.?\d*)", s)
                am = re.search(r"ask[:\s]*(\d+\.?\d*)", s)
                lm = re.search(r"last[:\s]*(\d+\.?\d*)", s)
                if bm and am and lm:
                    side = "YES" # Found via bid/ask logic
                else:
                    skipped_no_side += 1
                    offset += 8 + length
                    continue
            
            # Symbol check
            asym = "Unknown"
            s_upper = s.upper()
            tm = re.search(r'\b([A-Z]{1,8}[FGHJKMNQUVXZ]\d{1,2})\b', s_upper)
            if tm: asym = tm.group(1)
            else: asym = "CL" # Fallback since we are testing CL file
            
            if target_sym and target_sym not in asym:
                skipped_symbol_mismatch += 1
                offset += 8 + length
                continue
            
            p_val = float(pm.group(1))
            if p_val < 20 or p_val > 200:
                skipped_price_sanity += 1
                offset += 8 + length
                continue
            
            offset += 8 + length
        else:
            offset += 1

    print(f"Total 104 found: {total_104}")
    print(f"Skipped no keywords: {skipped_no_keywords}")
    print(f"Skipped no prices: {skipped_no_prices}")
    print(f"Skipped no side: {skipped_no_side}")
    print(f"Skipped symbol mismatch: {skipped_symbol_mismatch}")
    print(f"Skipped price sanity: {skipped_price_sanity}")

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
check_parser_skips(fp)
