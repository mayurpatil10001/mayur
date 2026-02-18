import requests

url = "http://localhost:8000/api/system/remove-cluster?account=CL-TS_6&symbol=CL"
try:
    print(f"Testing POST {url}")
    # Since I don't have real data now, it might delete 0 rows but should be 200
    response = requests.post(url)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
