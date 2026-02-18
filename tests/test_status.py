import requests

url = "http://localhost:8000/api/system/status"
try:
    print(f"Testing GET {url}")
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:100]}")
except Exception as e:
    print(f"Error: {e}")
