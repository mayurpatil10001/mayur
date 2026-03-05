path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"
with open(path, "rb") as f:
    f.seek(420)
    chunk = f.read(200)

print("Hex dump around offset 420:")
for i in range(0, len(chunk), 16):
    line = chunk[i:i+16]
    hex_str = " ".join(f"{b:02x}" for b in line)
    chars = "".join(chr(b) if 32 <= b <= 126 else "." for b in line)
    print(f"{420+i:04x} | {hex_str:<48} | {chars}")
