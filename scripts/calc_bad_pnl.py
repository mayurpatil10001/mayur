
import asyncio
import os
import sys

# Add project root to path
# Assuming this script is in C:\SierraChart\SC results WF\
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
print(f"DEBUG: sys.path prepended with: {sys.path[0]}")

from trading_platform.services.binary_log_parser import BinaryLogParser
import inspect
print(f"DEBUG: BinaryLogParser loaded from: {inspect.getfile(BinaryLogParser)}")

async def run_calc():
    print("Initializing BinaryLogParser...")
    parser = BinaryLogParser()
    
    # Path to SC logs
    sc_path = r"C:\SierraChart\SC results WF"
    
    print(f"Starting import for 3Q_SIM14 from {sc_path}...")
    # Trigger import - this will parse files, save to DB, AND run our modified purge_anomalies
    await parser.run_import(
        paths=[sc_path],
        filter_symbol="CL",
        account_filter=["3Q_SIM14"],
        # days_lookback=100 # Commented out to ensure we catch all files
        days_lookback=None
    )
    
    print("Import finished.")

if __name__ == "__main__":
    asyncio.run(run_calc())
