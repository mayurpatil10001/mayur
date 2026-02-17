import struct
import os

def examine_log(fp):
    with open(fp, 'rb') as f:
        d = f.read(10000) # first 10k bytes
    
    print(f"Examining {os.path.basename(fp)}...")
    offset = 0
    while offset < len(d) - 12:
        next_marker = d.find(b'\x00\x00\x00', offset + 1)
        if next_marker == -1: break
        offset = next_marker - 1
        tag = d[offset]
        length = struct.unpack('<I', d[offset+4 : offset+8])[0]
        
        if tag == 0x68: # Message
            val = d[offset+8 : offset+8+length].decode(errors='ignore')
            print(f"[{offset:04x}] TAG 0x68 (Msg) Len={length}: {val[:50]}...")
        elif tag == 0x66: # Time
            val_bytes = d[offset+8 : offset+8+length]
            print(f"[{offset:04x}] TAG 0x66 (Time) Len={length}: {val_bytes.hex()}")
        elif tag == 0x67: # Symbol
            val = d[offset+8 : offset+8+length].decode(errors='ignore')
            print(f"[{offset:04x}] TAG 0x67 (Sym) Len={length}: {val}")
        
        offset += 8 + length

if __name__ == "__main__":
    test_file = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.TS_4.data"
    examine_log(test_file)
