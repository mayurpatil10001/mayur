
import requests
import time
import json

BASE_URL = "http://localhost:8000"
LOG_PATH = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
SYMBOL = "CL"

def test_status():
    print("\n--- Testing System Status ---")
    try:
        resp = requests.get(f"{BASE_URL}/api/system/status", timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Stats: {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"Status check failed: {e}")

def test_scan():
    print(f"\n--- Testing Scan Logic for {SYMBOL} ---")
    payload = {
        "path": LOG_PATH,
        "symbol": SYMBOL
    }
    try:
        t0 = time.time()
        resp = requests.post(f"{BASE_URL}/api/system/check-path", json=payload, timeout=30)
        dur = time.time() - t0
        print(f"Status: {resp.status_code} (Duration: {dur:.2f}s)")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"Exists: {data.get('exists')}")
            print(f"File Count: {data.get('count')}")
            print(f"Message: {data.get('message')}")
            print(f"Accounts Found Count: {len(data.get('accounts'))}")
            # print(f"Accounts Found: {data.get('accounts')}") # Don't print huge list

        else:
            print(f"Error Response: {resp.text}")
            
    except Exception as e:
        print(f"Scan failed: {e}")

def test_restart():
    print("\n--- Testing Restart Endpoint ---")
    try:
        resp = requests.post(f"{BASE_URL}/api/system/restart", timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Restart trigger failed: {e}")


def test_import_status():
    print("\n--- Testing Import Status ---")
    try:
        resp = requests.get(f"{BASE_URL}/api/system/import-status", timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Details: {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"Import status check failed: {e}")

if __name__ == "__main__":
    test_status()
    test_import_status()

