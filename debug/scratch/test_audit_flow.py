import sqlite3
import os
import datetime
from audit_tool import parse_sc_pasted_data, compare_trades, fetch_db_trades

# MOCK SC DATA FOR DEC 18 (Including the 04:05:56 Ghost)
# Trade #	Account	Symbol	Side	Quantity	Entry Date Time	Exit Date Time	Entry Price	Exit Price	Profit/Loss
SC_MOCK_DATA = """
1	V_SIM16	NQZ25	SHORT	1	2025-12-18 04:05:56	2025-12-18 04:15:22	25313.75	25398.5	-1695.0
2	V_SIM16	NQZ25	LONG	1	2025-12-18 04:20:00	2025-12-18 04:30:00	25400.0	25410.0	200.0
"""

def test_audit():
    db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
    account = "V_SIM16"
    date_str = "2025-12-18"
    
    print(f"--- RUNNING AUTOMATED AUDIT TEST FOR {date_str} ---")
    
    # 1. Fetch from DB
    db_trades = fetch_db_trades(db_path, account, date_str)
    
    # 2. Parse Mock SC Data
    sc_trades = parse_sc_pasted_data(SC_MOCK_DATA.replace(' ', '\t')) # Ensure tabs
    
    # 3. Compare
    compare_trades(db_trades, sc_trades)

if __name__ == "__main__":
    test_audit()
