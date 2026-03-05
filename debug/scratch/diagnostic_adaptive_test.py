import os
import sys
import datetime

# Add current directory to path
sys.path.append(os.getcwd())

from trading_platform.services.binary_log_parser import _parse_file_nitro

def verify():
    base_path = "D:/SierraChart_Simulated_Feed/TradeActivityLogs"
    
    # 1. V_SIM16 (Expected: Ghosts blocked)
    vsim_file = os.path.join(base_path, "TradeActivityLog_2025-12-18_UTC.V_SIM16.data")
    if os.path.exists(vsim_file):
        fills, ghosts = _parse_file_nitro(vsim_file)
        print(f"\nV_SIM16 (12/18): Valid Fills: {len(fills)}, Ghosts: {len(ghosts)}")
        print("First 5 ghosts caught:")
        for g in ghosts[:5]:
            print(f" - {g['timestamp']} {g['side']} {g['price']} Note: '{g['note']}'")
        
        # Check for 04:05 NY time (09:05 UTC)
        found_target = any("T09:05" in g['timestamp'] for g in ghosts)
        print(f"V_SIM16 09:05 UTC (04:05 NY) Ghost Caught: {found_target}")
    
    # 2. TM_10 (Expected: No ghosts, because of bypass)
    tm10_file = os.path.join(base_path, "TradeActivityLog_2024-03-18_UTC.TM_10.data") # Using March 18 now
    if os.path.exists(tm10_file):
        fills, ghosts = _parse_file_nitro(tm10_file)
        print(f"\nTM_10 (03/18): Valid Fills: {len(fills)}, Ghosts: {len(ghosts)}")
        print(f"TM_10 Bypass Working (Ghosts==0): {len(ghosts) == 0}")

    # 3. CL-TM_10 (Check CL ghosts)
    cl_file = os.path.join(base_path, "TradeActivityLog_2024-03-24_UTC.CL-TM_10.data")
    if os.path.exists(cl_file):
        fills, ghosts = _parse_file_nitro(cl_file)
        print(f"\nCL-TM_10: Valid Fills: {len(fills)}, Ghosts: {len(ghosts)}")

verify()
