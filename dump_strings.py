import re
import os

def dump_strings(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Extract all ascii-like strings
    strings = re.findall(b'[\x20-\x7E]{10,}', data)
    for s in strings:
        try:
            val = s.decode('ascii')
            if any(x in val.lower() for x in ['profit', 'loss', 'trade', 'closed', 'entry', 'exit', 'filled']):
                print(val)
        except:
            pass

if __name__ == "__main__":
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_19550-12-05_UTC.ES-TM_3.data"
    if os.path.exists(path):
        dump_strings(path)
