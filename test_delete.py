import requests

url = "http://localhost:8000/api/system/delete-account?account=CL-TS_6&symbol=CL"
try:
    print(f"Testing DELETE {url}")
    response = requests.delete(url)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
