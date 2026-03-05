path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"
with open(path, "rb") as f:
    chunk = f.read(1000)

print("Hex dump of first 1000 bytes:")
for i in range(0, len(chunk), 16):
    line = chunk[i:i+16]
    hex_str = " ".join(f"{b:02x}" for b in line)
    chars = "".join(chr(b) if 32 <= b <= 126 else "." for b in line)
    print(f"{i:04x} | {hex_str:<48} | {chars}")
