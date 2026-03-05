from trading_platform.services.binary_log_parser import _parse_file_nitro, BinaryLogParser
import os
import sqlite3

fp = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-24_UTC.V_SIM16.data'
db_path = 'trading_platform.db'

parser = BinaryLogParser(db_path)

if os.path.exists(fp):
    fills = _parse_file_nitro(fp)
    print(f"Total fills: {len(fills)}")
    
    trades, unpaired, ghosts = parser._pairs_to_trades(fills, persist_state=False)
    print(f"Trades formed: {len(trades)}")
    print(f"Unpaired fills: {unpaired}")
    
    if trades:
        print("Sample trades:")
        for t in trades[:5]:
            print(t)
            
    # Check if they are being filtered by purge
    # We would need to 'save' them first to test purge, but we can just check the rule logic manually
    for t in trades:
        import datetime
        t1 = datetime.datetime.fromisoformat(t['entry_time'])
        t2 = datetime.datetime.fromisoformat(t['exit_time'])
        duration = (t2 - t1).total_seconds() / 3600
        if duration > 24:
            print(f"Trade would be PURGED (Duration: {duration:.2f}h): {t['entry_time']} -> {t['exit_time']}")
else:
    print("File not found")
