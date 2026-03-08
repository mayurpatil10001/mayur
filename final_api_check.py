import requests

def check_endpoint(url, label):
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            if 'accounts' in data: # Account management
                items = [a['account_name'] for a in data['accounts']]
            elif 'data' in data and 'items' in data['data']: # Paginated accounts
                items = [a['name'] for a in data['data']['items']]
            else:
                items = []
            
            vsim16 = [i for i in items if 'V_SIM16' in i]
            print(f"{label}: Found {len(items)} items. V_SIM16 matches: {vsim16}")
        else:
            print(f"{label}: Error {r.status_code}")
    except Exception as e:
        print(f"{label}: Exception {e}")

check_endpoint('http://localhost:8000/api/v1/accounts/?size=1000', 'List Accounts')
check_endpoint('http://localhost:8000/api/v1/accounts/management', 'Account Management')
check_endpoint('http://localhost:8000/api/system/accounts', 'System Accounts')
