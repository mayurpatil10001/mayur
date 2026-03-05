import os
import sys
import datetime
from zoneinfo import ZoneInfo

# Add standard paths
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import _parse_file_nitro

NY_TZ = ZoneInfo("America/New_York")

def scan_vsim16():
    base_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    # Files are like NQ_V_SIM16_20251218.data
    pattern = "NQZ25-V_SIM16_20251218.data"
    
    # Try multiple possible patterns
    files = [f for f in os.listdir(base_path) if "V_SIM16" in f and "20251218" in f]
    
    if not files:
        print("No binary files found for V_SIM16 on 12/18.")
        return

    for fn in files:
        fp = os.path.join(base_path, fn)
        print(f"\nScanning {fn}...")
        fills, note_rate = _parse_file_nitro(fp, account="V_SIM16")
        
        # Fills are raw candidates before filtering (as of current _parse_file_nitro)
        # Wait, _parse_file_nitro actually returns the FILTERED fills.
        # I want to see everything including the ghosts.
        
        # Let's look at the code of _parse_file_nitro to see how to get raw fills.
        # It buffers raw_candidates.
        
    print("\nFills found in DB-ready format:")
    for fill in fills:
        ts_utc = datetime.datetime.fromisoformat(fill['timestamp']).replace(tzinfo=datetime.timezone.utc)
        ts_ny = ts_utc.astimezone(NY_TZ)
        print(f"{ts_ny.strftime('%H:%M:%S')} | {fill['side']} {fill['quantity']} @ {fill['price']} | Note: '{fill.get('note','')}'")

if __name__ == "__main__":
    scan_vsim16()
