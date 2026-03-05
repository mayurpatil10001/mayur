path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"
with open(path, "rb") as f:
    data = f.read()
    
pos = 0
found = 0
while pos < len(data) - 65 and found < 10:
    if data[pos] == 0x82:
        print(f"Found Tag 0x82 at offset {pos}:")
        note_bytes = data[pos+1:pos+65]
        print(f"  Raw: {note_bytes.hex()}")
        print(f"  Decoded: {note_bytes.decode(errors='ignore').strip()}")
        found += 1
    pos += 1
