import os
log = 'trading_platform.log'
if os.path.exists(log):
    with open(log, 'rb') as f:
        data = f.read()
    if data.startswith(b'\xff\xfe'):
        data = data[2:]
    text = data.decode('utf-8', errors='replace')
    print("--- LAST 5000 BYTES ---")
    print(text[-5000:])
    if "Traceback" in text[-10000:]:
        print("\n!!! TRACEBACK FOUND !!!")
        idx = text.rfind("Traceback")
        print(text[idx:idx+2000])
else:
    print("Log not found")
