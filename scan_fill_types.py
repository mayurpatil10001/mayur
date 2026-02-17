import re
import os
import struct

def scan_message_types():
    # Pick a file that had fills
    fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2025-04-15_UTC.TS_4.data"
    
    with open(fp, 'rb') as f:
        d = f.read()
        
    offset = 0
    message_types = {}
    
    while offset < len(d) - 12:
        next_marker = d.find(b'\x00\x00\x00', offset + 1)
        if next_marker == -1: break
        offset = next_marker - 1
        tag = d[offset]
        length = struct.unpack('<I', d[offset+4 : offset+8])[0]
        
        if tag == 0x68: # Message
            s = d[offset+8 : offset+8+length].decode(errors='ignore')
            s_lower = s.lower()
            
            # Simple categorization
            category = "Other"
            if "auto-trade" in s_lower: category = "Auto-Trade"
            elif "trading evaluator" in s_lower: category = "Trading Evaluator"
            elif "order filled" in s_lower: category = "Order Filled"
            elif "fill" in s_lower: category = "Generic Fill"
            
            if category != "Other":
                if category not in message_types:
                    message_types[category] = []
                if len(message_types[category]) < 5:
                    message_types[category].append(s)
                    
        offset += 8 + length
        
    for cat, examples in message_types.items():
        print(f"\n--- {cat} ---")
        for ex in examples:
            print(f"  {ex.strip()}")

if __name__ == "__main__":
    scan_message_types()
