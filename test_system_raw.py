import requests

r = requests.get('http://localhost:8000/api/system/accounts')
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
