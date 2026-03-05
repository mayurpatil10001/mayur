import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from trading_platform.services.binary_log_parser import _parse_file_nitro

def compare_vsim16_messages():
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"
    fills, ghost_counts = _parse_file_nitro(path)
    
    targets = ['03:30:56', '03:31:07', '03:33:11']
    for f in fills:
        match = False
        for t in targets:
            if t in f['timestamp']: match = True
        
        if match:
            print(f"\n--- {f['timestamp']} ---")
            print(f"Side: {f['side']} | Qty: {f['quantity']}")
            print(f"Note: {f.get('note','')}")

if __name__ == "__main__":
    compare_vsim16_messages()
