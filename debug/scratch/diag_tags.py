import struct
import datetime
import os
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
TARGET = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

def _parse_tag66_timestamp(b: bytes):
    if len(b) >= 8:
        val = struct.unpack('<q', b[:8])[0]
        # SC timestamps are microseconds since 1899-12-30
        microseconds = val
        if microseconds > 0 and microseconds < 1e16:
            base = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
            delta = datetime.timedelta(microseconds=microseconds)
            return base + delta
    return None

def analyze_tags(file_path):
    print(f"Analyzing {file_path}")
    with open(file_path, 'rb') as f:
        d = f.read()

    file_len = len(d)
    offset = 0
    current_dt = None
    
    # We want to print ALL tags for fills around 04:05 and 04:18 NY time
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        if tag == 0 or tag > 512 or length > 65536:
            next_ptr = d.find(b'\x66\x00\x00\x00', offset + 1)
            if next_ptr == -1: break
            offset = next_ptr
            continue
            
        val_start = offset + 8
        val_end = val_start + length
        if val_end > file_len: break
        
        if tag == 102 or tag == 0x66: # Time
            new_dt = _parse_tag66_timestamp(d[val_start:val_end])
            if new_dt: current_dt = new_dt
            
        # Check if we are in the target window: around 04:05 NY or 04:18 NY
        if current_dt:
            ny = current_dt.astimezone(NY_TZ)
            target1 = (ny.hour == 4 and ny.minute == 5)
            target2 = (ny.hour == 4 and ny.minute >= 18 and ny.minute <= 20)
            
            if target1 or target2:
                # Let's decode the value
                try:
                    val_bytes = d[val_start:val_end]
                    # string heuristics
                    if b'\x00' in val_bytes:
                        val_str = val_bytes.split(b'\x00')[0].decode(errors='replace')
                    else:
                        val_str = val_bytes.decode(errors='replace')
                        
                    # double heuristics
                    if length == 8:
                        val_double = struct.unpack('<d', val_bytes)[0]
                    else:
                        val_double = 0
                        
                    # int heuristics
                    if length == 4:
                        val_int = struct.unpack('<i', val_bytes)[0]
                    else:
                        val_int = 0
                        
                    print(f"[{ny.strftime('%H:%M:%S.%f')}] TAG {tag} (0x{tag:X}): len={length} str='{val_str}' double={val_double} int={val_int}")
                except Exception as e:
                    pass
        
        offset = val_end

if __name__ == "__main__":
    analyze_tags(TARGET)
