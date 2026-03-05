import os
import sys

# Add the project path to sys.path
sys.path.append(r'c:\SierraChart\SC results WF')

from trading_platform.services.binary_log_parser import _parse_file_nitro, BinaryLogParser

parser = BinaryLogParser()

fp = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim13.data'
fills = _parse_file_nitro(fp, 'CL')
print(f"Total fills: {len(fills)}")

trades, unpaired = parser._pairs_to_trades(fills)
print(f"Trades formed: {len(trades)}")
print(f"Unpaired fills: {unpaired}")

if trades:
    for t in trades:
        print(f"Account: {t['account']} | Sym: {t['symbol']} | Trade: {t['entry_time']} to {t['exit_time']} | PnL: {t['profit_loss']}")
