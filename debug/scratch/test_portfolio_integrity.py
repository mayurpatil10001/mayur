import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1/analytics"
SYMBOL = "NQ"

def test_portfolio_differentiation():
    print(f"--- Testing Portfolio Differentiation for {SYMBOL} ---")
    
    # 1. Fetch discovery results
    url = f"{BASE_URL}/recommendations/discovery/{SYMBOL}?winners_only=true"
    response = requests.get(url)
    edges = response.json()["data"]["edges"]
    
    # 2. Find a split bin
    bin_map = {}
    split_bin = None
    for edge in edges:
        key = (edge["time_slot"], edge["day_of_week"])
        if key in bin_map:
            split_bin = key
            contenderA = bin_map[key]
            contenderB = edge
            break
        bin_map[key] = edge
        
    if not split_bin:
        print("SKIP: No split bin found in current dataset. Try ES or CL if NQ has one account dominating all.")
        return True
        
    print(f"Found split bin at {split_bin}. Contenders: {contenderA['account_name']} and {contenderB['account_name']}")
    
    # 3. Run portfolio backtest for A
    pt_url = f"{BASE_URL}/recommendations/backtest/portfolio"
    payloadA = {"symbol": SYMBOL, "edges": [contenderA]}
    responseA = requests.post(pt_url, json=payloadA)
    metricsA = responseA.json()["data"]["metrics"]
    
    # 4. Run portfolio backtest for B
    payloadB = {"symbol": SYMBOL, "edges": [contenderB]}
    responseB = requests.post(pt_url, json=payloadB)
    metricsB = responseB.json()["data"]["metrics"]
    
    print(f"A ({contenderA['account_name']}) PnL: {metricsA['total_pnl']}")
    print(f"B ({contenderB['account_name']}) PnL: {metricsB['total_pnl']}")
    
    if metricsA['total_pnl'] != metricsB['total_pnl']:
        print("SUCCESS: Portfolio backtesting distinguishes between different bin contenders.")
        return True
    else:
        # It's possible they have exact same PnL but different volume
        if metricsA['total_trades'] != metricsB['total_trades']:
            print("SUCCESS: Portfolio backtesting distinguishes via trade volume.")
            return True
        else:
            print("FAILURE: Different accounts in same bin produced identical portfolio results.")
            return False

if __name__ == "__main__":
    if not test_portfolio_differentiation():
        sys.exit(1)
