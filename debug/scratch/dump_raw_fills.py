import datetime as dt
import glob
from zoneinfo import ZoneInfo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trading_platform.services.binary_log_parser import _parse_file_nitro, _scan_position_fill_order
from tests.test_binary_benchmark_1218 import BINARY_GLOB_2D

ny = ZoneInfo("America/New_York")

position_order_list = []
for fp in sorted(glob.glob(BINARY_GLOB_2D)):
    position_order_list.extend(_scan_position_fill_order(fp))
position_order_map = {oid: i for i, oid in enumerate(position_order_list)}

out = []
for fp in sorted(glob.glob(BINARY_GLOB_2D)):
    fills, _ = _parse_file_nitro(fp, acc_filter=["V_SIM16"])
    for f in fills:
        ts_raw = f.get("trans_timestamp") or f["timestamp"]
        d_utc = dt.datetime.fromisoformat(ts_raw)
        if d_utc.tzinfo is None:
            d_utc = d_utc.replace(tzinfo=dt.timezone.utc)
        d_ny = d_utc.astimezone(ny).replace(tzinfo=None)
        
        # We need the 12-18 session: 12-17 18:00:00 to 12-18 17:00:00
        start_time = dt.datetime(2025, 12, 17, 18, 0, 0)
        end_time = dt.datetime(2025, 12, 18, 17, 0, 0)
        
        if start_time <= d_ny <= end_time:
            out.append(f)

# Sort by raw time
out.sort(key=lambda x: x.get('ts_val', 0))

print(f"{'Time NY':<23} | {'Side':<5} | {'Qty':<3} | {'Price':<8} | {'InternalOID':<15} | {'OrderID':<15} | {'PosAfter':<10} | {'Msg'}")
for f in out:
    ts_raw = f.get("trans_timestamp") or f["timestamp"]
    d_utc = dt.datetime.fromisoformat(ts_raw)
    if d_utc.tzinfo is None:
        d_utc = d_utc.replace(tzinfo=dt.timezone.utc)
    d_ny = d_utc.astimezone(ny).replace(tzinfo=None)
    
    t_str = d_ny.strftime("%H:%M:%S.%f")[:-3]
    t_str = str(t_str)
    io = str(f.get("internal_order_id", ""))
    pos_ord = str(position_order_map.get(io, "N/A"))
    oid = str(f.get("order_id", ""))
    pa = str(f.get("position_after", ""))
    msg = str(f.get("msgtxt", "")).strip().replace('\n', ' ')[:60]
    
    # Highlight the 02:26 one
    if "02:26" in t_str:
        print(">>> ", end="")
    p_str = str(f.get('price'))
    q_str = str(f.get('quantity'))
    print(f"{t_str:<23} | {f.get('side',''):<5} | {q_str:<3} | {p_str:<8} | {io:<15} | {oid:<15} | {pa:<10} | {pos_ord:<10} | {msg}")
