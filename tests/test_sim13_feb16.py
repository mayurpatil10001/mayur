from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

parser = BinaryLogParser()
fp = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-16_UTC.3Q_sim13.data'

print(f"--- PARSING FILE: {fp} ---")
fills = _parse_file_nitro(fp, "CL")
print(f"Total fills found: {len(fills)}")

trades, unpaired = parser._pairs_to_trades(fills)
print(f"Trades formed: {len(trades)}")
print(f"Unpaired fills: {unpaired}")

if trades:
    for t in trades:
        print(f"Trade: {t['entry_time']} to {t['exit_time']} | PnL: {t['profit_loss']}")

input_days = 7
import datetime
cutoff = (datetime.datetime.now() - datetime.timedelta(days=input_days)).timestamp()
mtime = os.path.getmtime(fp)
print(f"File mtime: {mtime} | Cutoff: {cutoff} | Included: {mtime >= cutoff}")
