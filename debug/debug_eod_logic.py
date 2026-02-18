import datetime
from zoneinfo import ZoneInfo
import sqlite3

NY_TZ = ZoneInfo("America/New_York")

def _to_ny(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        # Replicating the bug/feature in binary_log_parser.py
        return dt.replace(tzinfo=NY_TZ)
    return dt.astimezone(NY_TZ)

def check(t1_str, t2_str):
    t1 = datetime.datetime.fromisoformat(t1_str)
    t2 = datetime.datetime.fromisoformat(t2_str)
    t1_ny = _to_ny(t1)
    t2_ny = _to_ny(t2)
    
    drop = False
    if t1_ny.hour < 17 and (t2_ny.hour >= 18 or t2_ny.date() > t1_ny.date()):
        drop = True
        
    print(f"UTC (Naive): {t1_str} -> {t2_str}")
    print(f"NY (Assumed): {t1_ny} -> {t2_ny}")
    print(f"Hours: {t1_ny.hour} -> {t2_ny.hour}")
    print(f"DROP: {drop}")
    print("-" * 20)

print("--- SIMULATION OF EOD LOGIC ---")
# Trade from Feb 17
check("2026-02-17T08:51:45", "2026-02-17T09:20:10")

# Trade from Feb 16 (that exists in DB?)
check("2026-02-16T14:51:20", "2026-02-16T14:55:00")

# Hypothetical trade crossing 17:00 UTC (12:00 NY)
# 16:59 UTC -> 17:01 UTC
# If treated as NY: 16:59 NY -> 17:01 NY (GAP!)
check("2026-02-16T16:59:00", "2026-02-16T17:01:00")

