import os

def hex_dump(fp, size=4096):
    print(f"Hex dump of {fp} (first {size} bytes):")
    with open(fp, "rb") as f:
        data = f.read(size)
    
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_str = " ".join(f"{b:02x}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        print(f"{i:08x}  {hex_str:<47}  |{ascii_str}|")

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
if os.path.exists(fp):
    hex_dump(fp)
else:
    print("File not found.")
