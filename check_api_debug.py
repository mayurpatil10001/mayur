import requests

try:
    r = requests.get('http://localhost:8000/api/v1/accounts/debug')
    if r.status_code == 200:
        print(r.json())
    else:
        print(f"API Error: {r.status_code} - {r.text}")
except Exception as e:
    print(f"Error: {e}")
