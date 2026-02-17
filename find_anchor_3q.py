
import os

def find_anchors():
    f_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-19_UTC.3Q_sim14.data"
    target_price_offset = 2454
    account = b"3Q_sim14"
    
    with open(f_path, 'rb') as f:
        content = f.read()
    
    start = 0
    diffs = []
    while True:
        idx = content.find(account, start)
        if idx == -1: break
        diff = target_price_offset - idx
        if abs(diff) < 2000:
            diffs.append((idx, diff))
        start = idx + 1
        
    for idx, diff in diffs:
        print(f"Account at {idx}, Relative Price Offset: {diff}")

if __name__ == "__main__":
    find_anchors()
