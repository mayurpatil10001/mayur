path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"
with open(path, "rb") as f:
    data = f.read()
    
pos = 0
found = 0
while pos < len(data) - 8 and found < 10:
    if data[pos] == 0x6b:
        print(f"Found Tag 0x6b at offset {pos}: val={data[pos+8]}")
        found += 1
    pos += 1
