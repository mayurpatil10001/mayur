import sys
import os
from datetime import datetime

# Add the project root to sys.path so we can import our services
sys.path.append(os.getcwd())

from trading_platform.services.binary_log_parser import importer, _parse_file_nitro, _is_ghost_fill

def debug_import_file(file_path):
    print(f"Testing import of: {file_path}")
    
    # Parse the file
    fills = _parse_file_nitro(file_path)
    print(f"Parsed {len(fills)} total fills from binary.")
    
    if not fills:
        print("No fills found in file!")
        return

    if fills:
        print(f"Fill keys: {fills[0].keys()}")

    # Check first few fills
    for f in fills[:5]:
        ts = f.get('timestamp') or f.get('entry_time')
        print(f"  - Account: {f['account_name']}, Sym: {f['symbol']}, Side: {f['side']}, Note: {f['note']}, Time: {ts}")

    # Check for V_SIM16 specifically
    vsim_fills = [f for f in fills if f['account_name'].upper() == 'V_SIM16']
    print(f"Found {len(vsim_fills)} fills for V_SIM16.")
    
    if vsim_fills:
        # Check notes
        notes = set(f['note'] for f in vsim_fills)
        print(f"Notes found for V_SIM16: {notes}")
        
        # Run ghost check
        ghosts = [f for f in vsim_fills if _is_ghost_fill(f['account_name'], f['note'], f.get('timestamp') or f.get('entry_time'))]
        print(f"Ghost fills identified: {len(ghosts)}")
        if ghosts:
            print(f"Sample ghost note: {ghosts[0]['note']}")

    # Try to form trades
    trades, unpaired, dropped = importer._pairs_to_trades(fills, persist_state=False)
    print(f"Resulting Trades: {len(trades)}")
    print(f"Unpaired Fills Count: {unpaired}")
    print(f"Dropped Ghost Fills (Drift Guard): {len(dropped)}")
    
    acc_key = 'account_name' if trades and 'account_name' in trades[0] else 'account'
    vsim_trades = [t for t in trades if t.get(acc_key, '').upper() == 'V_SIM16']
    print(f"Trades for V_SIM16: {len(vsim_trades)}")
    if vsim_trades:
        print(f"Sample V_SIM16 Trade: {vsim_trades[0]}")

if __name__ == "__main__":
    target_file = "D:\\SierraChart_Simulated_Feed\\TradeActivityLogs\\TradeActivityLog_2025-11-05_UTC.V_sim16.data"
    debug_import_file(target_file)
