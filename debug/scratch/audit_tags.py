import struct

def audit_tags(path, limit=50):
    with open(path, "rb") as f:
        d = f.read()
    
    offset = 0
    count = 0
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        print(f"Off: {offset:06x} | Tag: {tag:3d} (0x{tag:02x}) | Len: {length}")
        offset += 8 + length
        count += 1
        if count >= limit: break

audit_tags(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
