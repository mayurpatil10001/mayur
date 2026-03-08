import requests

try:
    r = requests.get('http://localhost:8000/api/v1/accounts/?size=1000')
    if r.status_code == 200:
        data = r.json()
        accounts = [a['account_name'] for a in data.get('items', [])]
        vsim16 = [a for a in accounts if 'V_SIM16' in a]
        print(f"Total accounts found: {len(accounts)}")
        print(f"V_SIM16 accounts: {vsim16}")
    else:
        print(f"API Error: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
