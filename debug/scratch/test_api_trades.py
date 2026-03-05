import requests
import json

def check_api():
    url = "http://localhost:8000/api/v1/trades/"
    params = {
        "account_name": "V_SIM16",
        "sort": "DESC",
        "size": 1000
    }
    # Current user is likely authenticated, but the API might be open or using dev keys.
    # The start_trading_platform script might show how it's running.
    # Let's try without auth first if it's a dev environment.
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        print(resp.text)
        return

    data = resp.json()
    trades = data['data']['items']
    print(f"Total trades returned: {len(trades)}")
    if trades:
        print(f"First trade: {trades[0]['entry_time']}")
        print(f"Last trade: {trades[-1]['entry_time']}")
    
    found = False
    for t in trades:
        entry = t['entry_time']
        exit = t['exit_time']
        if "2025-12-18" in entry:
            print(f"{entry} -> {exit} | {t['side']} {t['quantity']} | PnL: {t['profit_loss']}")
            found = True
    if not found:
        print("No trades found on 12-18")

if __name__ == "__main__":
    check_api()
