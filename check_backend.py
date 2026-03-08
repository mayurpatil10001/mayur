import requests
import json

try:
    r = requests.get('http://localhost:8000/health')
    print(f"Health: {r.status_code}")
    print(json.dumps(r.json(), indent=2))
    
    r = requests.get('http://localhost:8000/api/system/accounts')
    print(f"System Accounts: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Count: {len(data)}")
        if data:
            vsim = [a for a in data if 'V_SIM16' in a.get('name', '')]
            print(f"V_SIM16 matches: {vsim}")
except Exception as e:
    print(f"Error: {e}")
