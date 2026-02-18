import os

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
if os.path.exists(fp):
    with open(fp, "rb") as f:
        data = f.read()
    print(f"File size: {len(data)}")
    print(f"Count of 'Trading Evaluator': {data.count(b'Trading Evaluator')}")
    print(f"Count of 'Fill': {data.count(b'Fill')}")
    print(f"Count of 'fill': {data.count(b'fill')}")
    print(f"Count of 'TS_4': {data.count(b'TS_4')}")
else:
    print("File not found")
