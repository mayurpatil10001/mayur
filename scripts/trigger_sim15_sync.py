import requests
import time

url = "http://localhost:8000/api/system/import-start"
payload = {
    "paths": ["D:\\SierraChart_Simulated_Feed\\TradeActivityLogs"],
    "symbol": "CL",
    "accounts": ["3Q_SIM15"],
    "days": 7
}

print(f"Triggering import for SIM15 CL...")
r = requests.post(url, json=payload)
print(f"Status Code: {r.status_code}")
print(f"Response: {r.json()}")

# Monitor progress
for _ in range(60):
    status_r = requests.get("http://localhost:8000/api/system/import-status")
    status = status_r.json()
    print(f"Progress: {status.get('progress')}% | Message: {status.get('message')}")
    if not status.get('running'):
        print(f"Final Stats: {status.get('stats')}")
        break
    time.sleep(2)
