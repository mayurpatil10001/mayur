import os
import sys

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills, _ = _parse_file_nitro(target_fp)
v_fills = [f for f in fills if f['account_name'] == 'V_SIM16']

print(f"Stats for {target_fp}:")
print(f"Total entries for V_SIM16: {len(v_fills)}")

# Production Dedupe Logic
seen_sigs = set()
deduped = []
for f in v_fills:
    sig = (round(f.get('ts_val', 0) * 2) / 2.0, f['price'], f['side'], f['quantity'])
    if sig not in seen_sigs:
        deduped.append(f)
        seen_sigs.add(sig)

print(f"After Dedupe: {len(deduped)}")

# Let's see how many have the same Note
with_note = [f for f in deduped if f.get('note')]
print(f"With Note: {len(with_note)}")
no_note = [f for f in deduped if not f.get('note')]
print(f"No Note: {len(no_note)}")
