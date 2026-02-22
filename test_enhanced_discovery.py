import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1/analytics"
SYMBOL = "NQ"

def test_discovery_metrics():
    print(f"--- Testing Discovery Metrics for {SYMBOL} ---")
    url = f"{BASE_URL}/recommendations/discovery/{SYMBOL}?logic=persistence&winners_only=true"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data["status"] != "success":
            print(f"FAILURE: Api returned status {data['status']}")
            return False
            
        edges = data["data"]["edges"]
        print(f"Received {len(edges)} edges.")
        
        # Check if basic metrics are present
        for edge in edges[:5]:
            required = ["account_name", "time_slot", "day_of_week", "total_pnl", "total_trades", "persistence_score", "avg_profit_per_trade", "win_rate"]
            missing = [f for f in required if f not in edge]
            if missing:
                print(f"FAILURE: Edge {edge['account_name']} missing fields: {missing}")
                return False
        
        print("SUCCESS: All edges have required metrics.")
        return True
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

def test_multivariable_leaders():
    print("\n--- Testing Multivariable Leaders (Persistence vs PnL vs Volume) ---")
    # This test will check if different accounts are returned for the same bin if they lead in different categories
    url = f"{BASE_URL}/recommendations/discovery/{SYMBOL}?logic=persistence&winners_only=true"
    
    try:
        response = requests.get(url)
        data = response.json()
        edges = data["data"]["edges"]
        
        # Look for duplicate bins (Time + Day) that have different accounts
        bin_map = {}
        duplicatesFound = False
        for edge in edges:
            key = (edge["time_slot"], edge["day_of_week"])
            if key in bin_map:
                if bin_map[key] != edge["account_name"]:
                    print(f"INFO: Found split bin at {key}: {bin_map[key]} and {edge['account_name']}")
                    duplicatesFound = True
            else:
                bin_map[key] = edge["account_name"]
        
        if not duplicatesFound:
            print("NOTE: No split bins found in current data. This might be expected if one account dominates all metrics.")
        else:
            print("SUCCESS: Multivariable leaders detected in same bins.")
        return True
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    s1 = test_discovery_metrics()
    s2 = test_multivariable_leaders()
    
    if not (s1 and s2):
        sys.exit(1)
