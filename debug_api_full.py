import requests

r = requests.get('http://localhost:8000/api/v1/accounts/?size=1000')
print(f"Status: {r.status_code}")
print(f"Body: {r.text}")
