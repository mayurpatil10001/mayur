
import os
import re

# Simulation of the check_path logic
target_symbol = "CL"
folder = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
files = [
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.3Q_sim14.data",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-14_UTC.3Q_sim14.data"
]

print(f"Scanning for {target_symbol} in {len(files)} files...")

found = False
for fp in files:
    try:
        size = os.path.getsize(fp)
        print(f"Checking {os.path.basename(fp)} ({size} bytes)")
        
        with open(fp, "rb") as f:
            # Check TAIL (Last 100KB)
            if size > 100*1024:
                f.seek(size - 100*1024)
            data = f.read()
            
            # Check Regex (Strict)
            pattern = rb'\b' + target_symbol.encode() + rb'[FGHJKMNQUVXZ]\d{1,2}\b'
            m = re.search(pattern, data, re.IGNORECASE)
            if m:
                print(f"  MATCH FOUND (Strict): {m.group().decode()}")
                found = True
                break
            else:
                print("  No strict match in tail.")
                
            # Check Simple Text
            if target_symbol.encode() in data.upper():
                 # This might be too loose ("CLUDE", "CLASS"), but main.py uses it only for .txt/.log
                 # main.py does NOT use this for .data files in the filtered loop?
                 # Let's check main.py code... it *does* check data.upper() but has a file extension check?
                 pass

            # Check HEAD (First 50KB) - strictly for test
            f.seek(0)
            head = f.read(50000)
            m_h = re.search(pattern, head, re.IGNORECASE)
            if m_h:
                print(f"  MATCH FOUND (Strict Head): {m_h.group().decode()}")
                found = True
                break
                
    except Exception as e:
        print(f"Error: {e}")

if found:
    print("SUCCESS: Account detected.")
else:
    print("FAILURE: Account NOT detected.")
