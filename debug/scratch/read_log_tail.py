import os
log = 'trading_platform.log'
if os.path.exists(log):
    with open(log, 'rb') as f:
        data = f.read()
    if data.startswith(b'\xff\xfe'):
        data = data[2:]
    text = data.decode('utf-8', errors='replace')
    print(text[-2000:])
else:
    print("Log not found")
