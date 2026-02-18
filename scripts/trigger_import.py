
import requests
import json

url = "http://localhost:8000/api/system/import-start"
payload = {
    "paths": [r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"],
    "symbol": "CL", # This filters specific fills if needed, or we can leave None
    "accounts": ["3Q_sim14"]
}

print(f"Triggering import for {payload['accounts']}...")
try:

    resp = requests.post(url, json=payload, timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")

    print("Monitoring status for 30 seconds...")
    import time
    for _ in range(15):
        time.sleep(2)
        try:
            s = requests.get("http://localhost:8000/api/system/import-status").json()
            print(f"Running: {s['running']} | Msg: {s['message']} | Found: {s['stats'].get('found',0)}")
            if not s['running'] and s['message'] != "Idle":
                print("Import Finished!")
                break
        except: pass

except Exception as e:
    print(f"Failed to trigger import: {e}")

