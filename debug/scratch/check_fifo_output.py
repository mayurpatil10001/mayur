"""
Check what FIFO _pairs_to_trades actually produces for V_SIM16 Dec 18.
We'll run the parser AND the pairing logic to see the raw trade output.
"""
import sys, os
sys.path.insert(0, r"C:\SierraChart\SC results WF")
os.chdir(r"C:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import _parse_file_nitro, BinaryLogParser
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

LOG_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
fills, ghosts = _parse_file_nitro(LOG_FILE)
fills.sort(key=lambda x: x.get("ts_val", 0))

print(f"Fills after dedup: {len(fills)}")

# Now run _pairs_to_trades directly  
parser = BinaryLogParser()
raw_trades = parser._pairs_to_trades(fills, "V_SIM16")

print(f"Raw trades from _pairs_to_trades: {len(raw_trades)}")

# Show 02:26 and 04:18 area
print("\n=== Raw trades in 02:00-05:00 NY zone ===")
for t in raw_trades:
    entry_str = t.get("entry_time", "")
    exit_str = t.get("exit_time", "")
    if not entry_str or not exit_str:
        continue
    try:
        e_dt = datetime.datetime.fromisoformat(entry_str).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        x_dt = datetime.datetime.fromisoformat(exit_str).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        if not (2 <= e_dt.hour < 5):
            continue
        side = t.get("side", "")
        qty = t.get("quantity", 0)
        pnl = t.get("profit_loss", 0)
        epx = t.get("entry_price", 0)
        xpx = t.get("exit_price", 0)
        drp = t.get("dropped_reason", "")
        flag = " <-- 02:26 LONG?" if e_dt.hour == 2 and e_dt.minute == 26 else ""
        flag = " DROPPED: " + drp if drp else flag
        print(f"  {e_dt.strftime('%H:%M:%S')} -> {x_dt.strftime('%H:%M:%S')} | {side} qty={qty} PnL={pnl:.2f} px={epx}/{xpx}{flag}")
    except Exception as ex:
        print(f"  ERROR: {ex}")
