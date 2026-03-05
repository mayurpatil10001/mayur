import requests
import json
import time

url = "http://localhost:8000/api/system/import-start"
data = {
    "paths": ["D:\\SierraChart_Simulated_Feed\\TradeActivityLogs"],
    "accounts": ["V_SIM16"],
    "symbol": "NQ",
    "days": 4000
}

r = requests.post(url, json=data)
if r.status_code == 200:
    print("Import started...")
    while True:
        s = requests.get("http://localhost:8000/api/system/import-status").json()
        pct, msg = s.get('progress', 0), s.get('message', '')
        print(f"P: {pct}% | {msg}")
        if pct >= 100 or "Complete" in msg:
            print(json.dumps(s['stats'], indent=2))
            break
        time.sleep(5)
else:
    print(f"Error starting: {r.status_code} {r.text}")
