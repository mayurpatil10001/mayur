import os
import sys
import datetime
import struct
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

def scan_raw_fills():
    fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_SIM16.DATA"
    if not os.path.exists(fp):
        print(f"File not found: {fp}")
        return

    print(f"Deep scanning raw candidates in {fp}...")
    
    with open(fp, "rb") as f:
        data = f.read()

    offset = 40
    # The parser uses a loop until EOF. 
    # Let's check the actual logic in binary_log_parser.py
    # It searches for specific tags.
    
    candidates = []
    
    # Simple search for "(Filled)" or "Trade simulation fill"
    for match_type in [b"(Filled)", b"Trade simulation fill"]:
        start = 0
        while True:
            start = data.find(match_type, start)
            if start == -1: break
            
            # Message Tag (104) is at offset 168 relative to record start.
            # So record_start = start - 168
            record_start = start - 168
            if record_start < 0: 
                start += 1
                continue
                
            try:
                # Timestamp Tag (48-55) is at record_start + 48
                ts_val = struct.unpack('d', data[record_start+48:record_start+56])[0]
                ts_dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=ts_val)
                ts_utc = ts_dt.replace(tzinfo=timezone.utc) if hasattr(datetime, "timezone") else ts_dt
                # Handle timezone
                ts_ny = (ts_dt + datetime.timedelta(hours=-5)).strftime('%H:%M:%S') # Rough estimate for speed
                
                # Note Tag (0x82) is at record_start + 392
                note = data[record_start+392:record_start+392+64].decode('ascii', errors='ignore').strip('\x00')
                msg = data[record_start+168:record_start+168+128].decode('ascii', errors='ignore').strip('\x00')
                
                if "02:2" in ts_ny:
                    print(f"{ts_ny} | MSG: {msg[:40]} | NOTE: '{note}'")
            except: pass
            
            start += 1

if __name__ == "__main__":
    scan_raw_fills()
