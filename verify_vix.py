
import requests
import json

base_url = "http://localhost:8000/api/vix-regime"

def test_endpoint(endpoint):
    print(f"Testing {endpoint}...")
    try:
        response = requests.get(f"{base_url}{endpoint}")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"First item: {json.dumps(data[0] if isinstance(data, list) else data, indent=2)}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
    print("-" * 30)

if __name__ == "__main__":
    # Note: These might fail if no VIX data is in the database or if auth is required
    # But since I enabled BearerAuth in main.py, I might need a token.
    # However, for local testing during development, sometimes it's disabled or I can skip it if I handle it in the router.
    # In my router I used Depends(require_read_permission), so I need a token.
    
    print("Pre-verification: checking if market_data has VIX")
    import sqlite3
    conn = sqlite3.connect("trading_platform.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM market_data WHERE symbol = 'VIX'")
    count = cursor.fetchone()[0]
    print(f"VIX records in DB: {count}")
    conn.close()

    # I'll skip the requests part if no token is available, or just try it.
    # test_endpoint("/data")
    # test_endpoint("/current")
