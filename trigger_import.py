import requests

paths = [
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_5\TradeActivityLogs"
]

payload = {
    "paths": paths,
    "symbol": "NQ",
    "accounts": ["V_SIM16"],
    "days": 2000
}

r = requests.post('http://localhost:8000/api/system/import-start', json=payload)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
