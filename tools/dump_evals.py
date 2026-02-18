import struct
import os

def dump_evaluators(fp):
    with open(fp, "rb") as f:
        data = f.read()
    
    offset = 0
    evaluators = set()
    while offset < len(data) - 12:
        try:
            tag = struct.unpack('<I', data[offset:offset+4])[0]
            length = struct.unpack('<I', data[offset+4:offset+8])[0]
            if tag == 104:
                val = data[offset+8 : offset+8+length].decode('ascii', errors='ignore')
                if "Evaluator" in val and val not in evaluators:
                    print(f"\n--- New Evaluator Message [{offset}] ---")
                    print(val)
                    evaluators.add(val)
                    if len(evaluators) >= 30: break
                offset += 8 + length
            else:
                offset += 1
        except:
            offset += 1

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-06_UTC.TS_4.data"
dump_evaluators(fp)
