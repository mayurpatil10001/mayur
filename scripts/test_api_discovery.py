import requests
import json

BASE_URL = "http://localhost:8000/api/analytics"

def test_endpoints():
    print("Testing Discovery Endpoint...")
    try:
        resp = requests.get(f"{BASE_URL}/recommendations/discovery/NQ?min_trades_total=50")
        if resp.status_code == 200:
            data = resp.json()
            print(f"SUCCESS: Found {len(data['data']['edges'])} edges for NQ")
            if data['data']['edges']:
                print(f"Top Edge: {data['data']['edges'][0]}")
        else:
            print(f"FAILED: Status {resp.status_code}, {resp.text}")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\nTesting Walk-Forward Validation Endpoint...")
    try:
        resp = requests.get(f"{BASE_URL}/recommendations/validation/walk-forward/NQ?min_persistence=70")
        if resp.status_code == 200:
            data = resp.json()
            print(f"SUCCESS: Total PnL: ${data['data']['metrics']['total_pnl']}")
            print(f"Equity points: {len(data['data']['equity_curve'])}")
        else:
            print(f"FAILED: Status {resp.status_code}, {resp.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_endpoints()
