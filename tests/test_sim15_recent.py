from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

parser = BinaryLogParser()
fps = [
    r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-16_UTC.3Q_sim15.data',
    r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim15.data'
]

for fp in fps:
    print(f"\n--- PARSING FILE: {fp} ---")
    fills = _parse_file_nitro(fp, "CL")
    print(f"Total fills found: {len(fills)}")

    trades, unpaired = parser._pairs_to_trades(fills)
    print(f"Trades formed: {len(trades)}")
    print(f"Unpaired fills: {unpaired}")

    if trades:
        # Show last 5 trades
        for t in trades[-5:]:
             print(f"Trade: {t['entry_time']} to {t['exit_time']} | PnL: {t['profit_loss']}")
