"""
Cross-file position boundary analysis for V_SIM16: Dec 17, 18, 19 UTC binary logs.
Answers: What position is carried over between days? Is there a 1-contract imbalance?
"""
import sys, os, datetime, glob
sys.path.insert(0, r"C:\SierraChart\SC results WF")
os.chdir(r"C:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import _parse_file_nitro
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

SEARCH_DIRS = [
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
]

def find_file(date_str):
    for d in SEARCH_DIRS:
        if not os.path.isdir(d):
            continue
        p = os.path.join(d, f"TradeActivityLog_{date_str}_UTC.V_sim16.data")
        if os.path.exists(p):
            return p
        all_f = glob.glob(os.path.join(d, f"*{date_str}*sim16*.data"), recursive=False)
        if all_f:
            return all_f[0]
    return None

def trace_file(date_str, start_net=0):
    path = find_file(date_str)
    if not path:
        print(f"\n[{date_str}] FILE NOT FOUND")
        return start_net

    fills, ghosts = _parse_file_nitro(path)
    fills.sort(key=lambda x: x.get("ts_val", 0))

    print(f"\n{'='*65}")
    print(f"[{date_str}] {os.path.basename(path)}")
    print(f"  Fills={len(fills)}, Ghosts={len(ghosts)}, Starting net={start_net:+d}")

    # Ghosts
    for g in ghosts:
        ts = g.get("timestamp", "")
        try:
            dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
            ts_str = dt.strftime("%m/%d %H:%M:%S")
        except:
            ts_str = ts
        print(f"  GHOST: {ts_str} | {g.get('side','')} {g.get('quantity','')} @ {g.get('price','')} | note='{g.get('note','')}'")

    # Walk fills tracking net position
    net = start_net
    # Collect all LONG/SHORT-breaking fills (qty not divisible by 3 and not matching the pattern)
    anomalies = []
    for f in fills:
        side = f.get("side", "")
        qty = f.get("quantity", 0)
        note = f.get("note", "")
        prev_net = net
        if side == "BUY":
            net += qty
        elif side == "SELL":
            net -= qty

        # Flag any fill that creates a position not divisible by 3 (strategy always trades in 3s)
        if net % 3 != 0:
            ts = f.get("timestamp", "")
            try:
                dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
                ts_str = dt.strftime("%m/%d %H:%M:%S")
            except:
                ts_str = ts
            anomalies.append((ts_str, side, qty, net, note[:30]))

    print(f"  Ending net position: {net:+d}")

    if net % 3 != 0:
        print(f"  *** NON-ZERO / NON-MULTIPLE-OF-3 at end: {net:+d} ***")
    elif net != 0:
        print(f"  *** POSITION NOT FLAT at end: {net:+d} contracts carry to next file ***")
    else:
        print(f"  OK - position flat at end of file.")

    if anomalies:
        print(f"\n  Fills that broke 3-lot pattern ({len(anomalies)} occurrences):")
        for a in anomalies[:15]:
            print(f"    {a[0]} {a[1]:5s} {a[2]:2d}  net→{a[3]:+4d}  note: {a[4]}")
        if len(anomalies) > 15:
            print(f"    ... ({len(anomalies)-15} more)")

    # Show position at file boundary (last 5 fills)
    print(f"\n  Last 5 fills:")
    for f in fills[-5:]:
        ts = f.get("timestamp", "")
        try:
            dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
            ts_str = dt.strftime("%m/%d %H:%M:%S")
        except:
            ts_str = ts
        print(f"    {ts_str} {f.get('side',''):5s} {f.get('quantity',0):2d} @ {f.get('price',0):10} note: {f.get('note','')[:25]}")

    return net

# ---- Run ----
print("V_SIM16 CROSS-FILE BOUNDARY ANALYSIS (Dec 17-18-19)")

net17 = trace_file("2025-12-17", start_net=0)
net18 = trace_file("2025-12-18", start_net=net17)
net19 = trace_file("2025-12-19", start_net=net18)

print(f"\n{'='*65}")
print("CARRYOVER SUMMARY:")
print(f"  Dec 17 end: {net17:+d}  →  carries into Dec 18")
print(f"  Dec 18 end: {net18:+d}  →  carries into Dec 19")
print(f"  Dec 19 end: {net19:+d}")

# The CORRECT expected carryover:
# If strategy is flat at session end (17:00 NY daily), carryover = 0
# If non-zero, it means either:
# A) Ghost fills slipped through (wrong direction, creating imbalance)
# B) EOD flattening fills are being mis-parsed or ignored
# C) Partial fills were NOT deduplicated

print()
if net17 != 0:
    print(f"ROOT CAUSE FOUND: Dec 17 ends {net17:+d}, not flat.")
    print(f"  The {net17:+d} carries into Dec 18, shifting all subsequent FIFO pairings.")
    print(f"  Fix: ensure EOD close fills in Dec 17 correctly bring position to 0.")
