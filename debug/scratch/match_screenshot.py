import os
import sys
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills_clean, ghost_map_clean = _parse_file_nitro(target_fp)

v_clean = [f for f in fills_clean if f['account_name'] == 'V_SIM16']
v_clean.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

# Now let's compare our fills with the screenshot
# User's screenshot shows fills starting with:
# 02:12:05.598  SELL 2  OID 36782318 => but that's in the middle
# Let me match the first fills with the screenshot
# Screenshot first fill: 02:12:48.3348 -> OID 36782482 -> Stop Limit -> 2 -> V_Sell

# Let me check: are we reading from the START of the trading day?
# SC trading day starts at 17:00 NY previous day (= 22:00 UTC)
# File is dated 2025-12-18 UTC
# Fill #1 is at 00:01:42.504 UTC = 19:01:42 NY (Dec 17)

# But user's screenshot shows fills starting at 02:12 NY (Dec 18) = 07:12 UTC
# Let me check what fills we have vs the user's screenshot

# User's screenshot (third image) shows these fills in order:
# 02:02:05.5981 -> OID 36782318 -> Trailing Stop -> 1 -> V_Sell
# 02:12:14.2965 -> OID 36782481 -> Market -> 3 -> V_Buy
# etc

# My parser gives fills starting at 00:01:42 UTC = 19:01 NY
# But the SC TAL window says Date: 2025-12-18, so it's the 12/18 session
# SC session for 12/18 starts at 17:00 NY on 12/17 = 22:00 UTC on 12/17
# But this file is TradeActivityLog_2025-12-18_UTC -> UTC date

# Let me check: does the user's screenshot show FILLS or TRADES?
# The first screenshot header says "Fills | NonSim | NQ## | V_sim16"
# The timestamps show NY time: 02:12:48 etc

# My fill #1 at 00:01:42 UTC = 19:01 NY Dec 17 -> this is BEFORE the session date
# Let me see how many fills are before the 12/18 session (before 22:00 UTC Dec 17)

# Actually my file is 2025-12-18_UTC, so all timestamps are on Dec 18 UTC
# 00:01:42 UTC Dec 18 = 19:01 NY Dec 17 -> Before EOD
# This fill at 19:01 NY is AFTER the 17:00 NY close -> it's the new session (Dec 18)

# So the user's first screenshot starts at 02:12 NY = 07:12 UTC
# But I have fills starting at 00:01 UTC = 19:01 NY
# The user's filter might start at a different time

# KEY QUESTION: Does the user's fill list match mine?
# Let me match OIDs from the screenshot to my fills

target_oids = ['36782318', '36782481', '36782483', '36782482', '36782518', '36782526', '36782525',
               '36782689', '36783140', '36783303', '36783314', '36783708']

print("Matching OIDs from screenshot to my parser output:")
for oid in target_oids:
    match = [f for f in v_clean if str(f.get('order_id', '')).startswith(oid)]
    if match:
        f = match[0]
        print(f"  OID {oid}: {f['timestamp'][:23]} | {f['side']:5} Qty:{f['quantity']} | Price:{f['price']} | Note:'{f.get('note','')[:20]}'")
    else:
        print(f"  OID {oid}: NOT FOUND IN PARSER OUTPUT")

# Now let's specifically check the ghost at 36783140
print("\n--- Checking ghost OID 36783140 ---")
ghost_found = [f for f in v_clean if str(f.get('order_id', '')).startswith('36783140')]
if ghost_found:
    print(f"  GHOST IS IN CLEAN FILLS! It was NOT removed as ghost!")
    print(f"  {ghost_found[0]}")
else:
    print(f"  Ghost was correctly removed from fill list")
