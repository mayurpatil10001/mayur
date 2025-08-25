#!/usr/bin/env python3
"""
Check which files have numeric values in the Account column.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from trading_platform.services.processed_trade_parser import SierraChartProcessedTradeParser
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

parser = SierraChartProcessedTradeParser(logger)

# Directories to check
directories = [
    "D:\\SierraChart_Simulated_Feed\\SierraChartInstance_5\\SavedTradeActivity",
    "D:\\SierraChart_Simulated_Feed\\SavedTradeActivity", 
    "D:\\SierraChart_Delayed_Simulated\\SavedTradeActivity",
    "D:\\SierraChart_Simulated_Feed\\SierraChartInstance_4\\SavedTradeActivity"
]

print("Checking files for numeric account names...")
print("=" * 80)

for directory in directories:
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Directory does not exist: {directory}")
        continue
    
    print(f"\nChecking directory: {directory}")
    
    for file_path in dir_path.glob("*.txt"):
        try:
            records = parser.parse_file(file_path)
            if records:
                first_account = records[0].account
                if first_account.isdigit():
                    print(f"  🔴 NUMERIC ACCOUNT: {file_path.name}")
                    print(f"      Account column value: '{first_account}'")
                    print(f"      Total records: {len(records)}")
                    
                    # Check a few more records to see if they're all numeric
                    sample_accounts = set()
                    for i, record in enumerate(records[:10]):
                        sample_accounts.add(record.account)
                    print(f"      Sample accounts: {sample_accounts}")
                    print()
                else:
                    print(f"  ✅ Proper account: {file_path.name} -> '{first_account}'")
        except Exception as e:
            print(f"  ❌ Error parsing {file_path.name}: {e}")

print("\nDone!")