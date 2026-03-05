import os
import sys

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills, _ = _parse_file_nitro(target_fp)
v_fills = [f for f in fills if f['account_name'] == 'V_SIM16']

net_pos = 0
limit = 3
drift_notes = {}

for f in v_fills:
    side, qty, note = f['side'], f['quantity'], f.get('note', '')
    if side == 'BUY':
        intended = net_pos + qty
        if intended > limit:
            drift_notes[note] = drift_notes.get(note, 0) + 1
            qty = max(0, limit - net_pos)
        net_pos += qty
    else:
        intended = net_pos - qty
        if intended < -limit:
            drift_notes[note] = drift_notes.get(note, 0) + 1
            qty = max(0, limit + net_pos)
        net_pos -= qty

print(f"Drift Note Breakdown for {target_fp}:")
for n, c in drift_notes.items():
    print(f"  Count: {c:3d} | Note: '{n}'")
