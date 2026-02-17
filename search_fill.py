import struct
import re
import os

def search_fill_data(fp, price):
    with open(fp, "rb") as f:
        data = f.read()
    
    # 1. Search for price as string
    price_str = f"{price:.2f}".encode()
    for m in re.finditer(re.escape(price_str), data):
        print(f"String '{price_str.decode()}' found at {m.start()}")
        print(f"Context: {data[max(0, m.start()-100):m.start()+100].decode('ascii', errors='ignore')}")
    
    # 2. Search for price as double (8 bytes)
    price_double = struct.pack('<d', price)
    for m in re.finditer(re.escape(price_double), data):
        print(f"Double '{price}' found at {m.start()} (Hex: {price_double.hex()})")
        # Dump tags around this offset
        dump_tags_nearby(data, m.start())

def dump_tags_nearby(data, center):
    start = max(0, center - 128)
    end = min(len(data), center + 128)
    print(f"--- Dumping tags around {center} ---")
    offset = start
    while offset < end - 8:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        if 0 < length < 10000 and 0 < tag < 200:
            val = data[offset+8 : offset+8+length]
            print(f"  [{offset:08x}] Tag {tag} | Len {length} | Val: {val.hex()} | {val.decode('ascii', errors='ignore')}")
            offset += 8 + length
        else:
            offset += 1

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-06_UTC.TS_4.data"
search_fill_data(fp, 64.25)
