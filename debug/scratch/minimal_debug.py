import sys
import os
from datetime import datetime

# Add the project root to sys.path so we can import our services
sys.path.append(os.getcwd())

from trading_platform.services.binary_log_parser import importer, _parse_file_nitro, _is_ghost_fill

def debug_import_file(file_path):
    fills = _parse_file_nitro(file_path)
    trades, unpaired, dropped = importer._pairs_to_trades(fills, persist_state=False)
    
    print(f"FILE: {os.path.basename(file_path)}")
    print(f"PARSED_FILLS: {len(fills)}")
    print(f"RESULTING_TRADES: {len(trades)}")
    print(f"UNPAIRED_FILLS_COUNT: {unpaired}")
    print(f"DROPPED_GHOST_FILLS: {len(dropped)}")
    
    if trades:
        vsim_trades = [t for t in trades if t.get('account_name', t.get('account', '')).upper() == 'V_SIM16']
        print(f"VSIM16_TRADES: {len(vsim_trades)}")
        if vsim_trades:
            print(f"EXAMPLE_PNL: {vsim_trades[0].get('profit_loss')}")

if __name__ == "__main__":
    target_file = "D:\\SierraChart_Simulated_Feed\\TradeActivityLogs\\TradeActivityLog_2025-11-25_UTC.V_sim16.data"
    debug_import_file(target_file)
