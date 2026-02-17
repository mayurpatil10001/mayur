
import requests
import json

url = "http://localhost:8000/api/system/check-path"
path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
payload = {"path": path}

try:
    print(f"Testing URL: {url}")
    print(f"Payload: {payload}")
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
