import requests
import json
import time

url = "http://localhost:8000/api/system/import-start"
status_url = "http://localhost:8000/api/system/import-status"

payload = {
    "days": 2000, 
    "accounts": ["3Q_SIM13", "3Q_SIM14", "3Q_SIM15"],
    "symbol": "CL",
    "paths": [r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"]
}

print(f"Triggering FULL import...")
requests.post(url, json=payload)

while True:
    try:
        r = requests.get(status_url)
        data = r.json()
        if not data.get('running', False):
            print("\nDone.")
            print(data.get('message'))
            break
        print(f"\rProgress: {data.get('progress', 0)}% | {data.get('message', '')[:60]}", end="")
        time.sleep(2)
    except: break
