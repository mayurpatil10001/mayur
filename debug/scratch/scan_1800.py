import glob
import struct
import datetime as dt
from zoneinfo import ZoneInfo

BINARY_GLOB = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-1[789]_UTC.V_sim16.data"
ny = ZoneInfo("America/New_York")

def _parse_tag66_timestamp(b: bytes) -> dt.datetime | None:
    if len(b) != 8: return None
    try:
        tval = struct.unpack('<q', b)[0]
        microseconds = tval % 1000000
        seconds = tval // 1000000
        epoch_start = dt.datetime(1899, 12, 30, tzinfo=dt.timezone.utc)
        return epoch_start + dt.timedelta(seconds=seconds, microseconds=microseconds)
    except: return None

with open("scan_1800_out_utf8.txt", "w", encoding="utf-8") as out:
    for f_path in glob.glob(BINARY_GLOB):
        out.write(f"Scaning file: {f_path}\n")
        with open(f_path, "rb") as f:
            d = f.read()
        
        offset = 0
        file_len = len(d)
        current_dt = None
        
        while offset < file_len - 8:
            tag, length = struct.unpack('<II', d[offset:offset+8])
            if tag == 0 or tag > 512 or length > 65536:
                ptr = d.find(b'\x66\x00\x00\x00', offset+1)
                if ptr == -1: break
                offset = ptr
                continue
            
            v_start = offset + 8
            v_end = v_start + length
            
            if tag == 102 or tag == 0x66:
                utc_dt = _parse_tag66_timestamp(d[v_start:v_end])
                if utc_dt:
                    current_dt = utc_dt.astimezone(ny).replace(tzinfo=None)
            
            if tag == 104 and current_dt:
                if current_dt.date() == dt.date(2025, 12, 17) and 17 <= current_dt.hour <= 18:
                    msg = d[v_start:v_end].decode('utf-8', errors='ignore').strip().replace('\0', '')
                    # We care about fills
                    if "buy" in msg.lower() or "sell" in msg.lower() or "filled" in msg.lower():
                        out.write(f"{current_dt.isoformat()} : {msg}\n")
            
            offset = v_end
