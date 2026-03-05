import struct, datetime, os

def dump_tags(path, limit=1000):
    if not os.path.exists(path):
        print("File not found")
        return
        
    with open(path, 'rb') as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    found = 0
    
    while offset < file_len - 8 and found < limit:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        # Print tag and length
        print(f"Tag: {tag:<4} | Len: {length:<6} | Off: {offset:<10}")
        found += 1
        
        offset += 8 + length

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
dump_tags(path)
