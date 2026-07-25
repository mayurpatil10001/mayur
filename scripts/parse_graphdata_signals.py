"""
scripts/parse_graphdata_signals.py
====================================
Parses the TM_7_NQU26 GraphData export, extracts Buy/Sell bar signals,
matches them to raw binary log fills (from dataset/*.data files),
and produces a Google Sheets-importable CSV showing:
- Date, Bar Time, Direction, Entry Price, Target Prices, Stop Loss
- Plus matching raw fills for TM_7 account NQU26 on those same days.

Outputs: docs/tm7_nqu26_signal_to_trade_match.csv (3 trading days only)
"""

import os
import struct
import datetime
import csv
from pathlib import Path
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
PROJECT_ROOT = Path(__file__).parent.parent

GRAPHDATA_FILE = PROJECT_ROOT / "TM_7_NQU26 [CBV][M]  1000 Volume #5_GraphData (1).txt"
DATASET_DIR = PROJECT_ROOT / "dataset"
OUTPUT_CSV = PROJECT_ROOT / "docs" / "tm7_nqu26_signal_to_trade_match.csv"

# Column indices (0-based)
COL_DATE = 0
COL_TIME = 1
COL_OPEN = 2
COL_HIGH = 3
COL_LOW = 4
COL_LAST = 5
COL_VOLUME = 6
COL_NUM_TRADES = 7
COL_BID_VOL = 11
COL_ASK_VOL = 12
COL_BUY_PRICE = 13          # Non-zero = BUY signal fired
COL_SELL_PRICE = 14         # Non-zero = SELL signal fired
COL_SELL_TARGET1 = 15
COL_BUY_TARGET1 = 16
COL_SELL_STOPLOSS = 17
COL_BUY_STOPLOSS = 18
COL_BUY_ENTRY = 19
COL_SELL_ENTRY = 20
COL_AUTO_TRADER_BUY = 30    # Non-zero = automated buy execution confirmed
COL_AUTO_TRADER_SELL = 31   # Non-zero = automated sell execution confirmed

TARGET_ACCOUNT = "TM_7"
TARGET_SYMBOL = "NQU26"


def parse_graphdata(filepath, num_days=3):
    """Parse signals from the GraphData CSV, return first num_days of signal bars."""
    signals = []
    seen_dates = []

    with open(str(filepath), "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines[1:]:  # skip header
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 35:
            continue
        try:
            date_str = parts[COL_DATE]
            time_str = parts[COL_TIME]
            buy_price = float(parts[COL_BUY_PRICE])
            sell_price = float(parts[COL_SELL_PRICE])
            auto_buy = float(parts[COL_AUTO_TRADER_BUY])
            auto_sell = float(parts[COL_AUTO_TRADER_SELL])
            buy_target1 = float(parts[COL_BUY_TARGET1])
            sell_target1 = float(parts[COL_SELL_TARGET1])
            buy_stop = float(parts[COL_BUY_STOPLOSS])
            sell_stop = float(parts[COL_SELL_STOPLOSS])
            open_p = float(parts[COL_OPEN])
            high_p = float(parts[COL_HIGH])
            low_p = float(parts[COL_LOW])
            last_p = float(parts[COL_LAST])
            volume = int(float(parts[COL_VOLUME]))
            bid_vol = int(float(parts[COL_BID_VOL]))
            ask_vol = int(float(parts[COL_ASK_VOL]))
        except (ValueError, IndexError):
            continue

        # Only capture signal bars (Buy or Sell entry fired)
        is_buy_signal = buy_price > 0
        is_sell_signal = sell_price > 0
        is_auto_trade = auto_buy > 0 or auto_sell > 0

        if not (is_buy_signal or is_sell_signal):
            continue

        # Track unique dates, stop after num_days
        if date_str not in seen_dates:
            if len(seen_dates) >= num_days:
                break
            seen_dates.append(date_str)

        if date_str not in seen_dates:
            continue

        direction = "BUY" if is_buy_signal else "SELL"
        entry_price = buy_price if is_buy_signal else sell_price
        target1 = buy_target1 if is_buy_signal else sell_target1
        stop = buy_stop if is_buy_signal else sell_stop
        auto_executed = "YES" if is_auto_trade else "NO"

        signals.append({
            "date": date_str,
            "bar_time": time_str,
            "direction": direction,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": last_p,
            "entry_price": entry_price,
            "target1": target1,
            "stop_loss": stop,
            "volume": volume,
            "bid_vol": bid_vol,
            "ask_vol": ask_vol,
            "auto_executed": auto_executed,
        })

    return signals, seen_dates


def parse_raw_binary_fills(dataset_dir, account, symbol, dates_yyyymmdd):
    """
    Read TM_7 binary activity log files for given dates.
    Extract raw fills matching the symbol (NQU26).
    Returns list of raw fill dicts.
    """
    fills = []
    for date_str in dates_yyyymmdd:
        # Normalize date format: 2026-6-10 -> 2026-06-10
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.datetime.strptime(date_str, "%Y-%#m-%#d")
            except:
                # Try manual parse for "2026-6-10" style
                parts = date_str.split("-")
                dt = datetime.datetime(int(parts[0]), int(parts[1]), int(parts[2]))

        iso_date = dt.strftime("%Y-%m-%d")

        # Find matching binary file for TM_7 on this date
        pattern = os.path.join(str(dataset_dir), f"TradeActivityLog_{iso_date}_UTC.TM_7.data")
        if os.path.exists(pattern):
            fills_from_file = extract_fills_from_binary(pattern, symbol)
            for f in fills_from_file:
                f["date"] = iso_date
                f["account"] = account
            fills.extend(fills_from_file)
        else:
            fills.append({
                "date": iso_date,
                "account": account,
                "symbol": symbol,
                "time": "N/A",
                "side": "N/A",
                "price": 0,
                "qty": 0,
                "note": f"No binary file found: {pattern}",
            })

    return fills


def extract_fills_from_binary(file_path, symbol_filter):
    """
    Minimal TLV binary parser to extract fill records from a Sierra Chart .data file.
    Searches for message text containing fill information and symbol matching.
    """
    fills = []
    try:
        with open(file_path, "rb") as bf:
            data = bf.read()
    except Exception as e:
        return fills

    n = len(data)
    pos = 0
    current_ts = None

    while pos + 8 <= n:
        try:
            tag = struct.unpack("<I", data[pos:pos+4])[0]
            length = struct.unpack("<I", data[pos+4:pos+8])[0]
            val_start = pos + 8
            val_end = val_start + length

            if val_end > n or length > 2_000_000:
                pos += 8
                continue

            val = data[val_start:val_end]

            # Tag 0x66 = Timestamp
            if tag == 0x66 and length >= 8:
                try:
                    v = struct.unpack("<d", val[:8])[0]
                    if 30000 < v < 70000:
                        base = datetime.datetime(1899, 12, 30)
                        current_ts = base + datetime.timedelta(days=v)
                except:
                    pass

            # Tag 0x68 (104) or tag 0x58 = message text
            elif tag in (0x68, 0x58, 104, 88):
                try:
                    text = val.decode("utf-8", errors="ignore")
                    text_l = text.lower()

                    # Look for fill events
                    if ("trade simulation fill" in text_l or "fill:" in text_l or "(filled)" in text_l):
                        # Check symbol match
                        if symbol_filter.upper() in text.upper() or symbol_filter[:3].upper() in text.upper():
                            side = "BUY" if any(x in text_l for x in ["buy", "long"]) else (
                                   "SELL" if any(x in text_l for x in ["sell", "short"]) else "UNKNOWN")

                            import re
                            pm = re.search(r"(?:fillprice|price)[:\s]*([\d]+\.?[\d]*)", text_l)
                            price = float(pm.group(1)) if pm else 0.0

                            qm = re.search(r"(?:qty|quantity)[:\s]*(\d+)", text_l)
                            qty = int(qm.group(1)) if qm else 1

                            ts_str = current_ts.strftime("%H:%M:%S") if current_ts else "?"
                            fills.append({
                                "symbol": symbol_filter,
                                "time": ts_str,
                                "side": side,
                                "price": price,
                                "qty": qty,
                                "note": text[:120].strip(),
                            })
                except:
                    pass

            pos = val_end

        except Exception:
            pos += 8

    return fills


def main():
    print("Parsing GraphData signal file...")
    signals, active_dates = parse_graphdata(GRAPHDATA_FILE, num_days=3)

    print(f"3 Trading Days Selected: {active_dates}")
    print(f"Total Bar Signals Found: {len(signals)}")

    print("\nParsing raw binary fills for TM_7 / NQU26 on those days...")
    raw_fills = parse_raw_binary_fills(DATASET_DIR, TARGET_ACCOUNT, TARGET_SYMBOL, active_dates)
    print(f"Total Raw Fills Found: {len(raw_fills)}")

    os.makedirs(str(OUTPUT_CSV.parent), exist_ok=True)

    # Write CSV
    with open(str(OUTPUT_CSV), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Section 1: Bar Signal List
        writer.writerow(["=== SECTION 1: BAR SIGNAL LIST (from GraphData) ==="])
        writer.writerow(["Date", "Bar_Time_NY", "Direction", "Open", "High", "Low", "Close",
                         "Entry_Price", "Target1_Price", "Stop_Loss_Price",
                         "Bar_Volume_1000", "Bid_Volume", "Ask_Volume", "Auto_Executed"])
        for s in signals:
            writer.writerow([
                s["date"], s["bar_time"], s["direction"],
                s["open"], s["high"], s["low"], s["close"],
                s["entry_price"], s["target1"], s["stop_loss"],
                s["volume"], s["bid_vol"], s["ask_vol"], s["auto_executed"]
            ])

        writer.writerow([])
        writer.writerow(["=== SECTION 2: DAILY SIGNAL SUMMARY ==="])
        writer.writerow(["Date", "Total_Buy_Signals", "Total_Sell_Signals", "Total_Signals"])
        from collections import defaultdict
        day_counts = defaultdict(lambda: {"buy": 0, "sell": 0})
        for s in signals:
            if s["direction"] == "BUY":
                day_counts[s["date"]]["buy"] += 1
            else:
                day_counts[s["date"]]["sell"] += 1
        for d in active_dates:
            dc = day_counts.get(d, {"buy": 0, "sell": 0})
            writer.writerow([d, dc["buy"], dc["sell"], dc["buy"] + dc["sell"]])

        writer.writerow([])
        writer.writerow(["=== SECTION 3: RAW BINARY FILLS FOR TM_7 / NQU26 (from dataset binary files) ==="])
        writer.writerow(["Date", "Account", "Symbol", "Fill_Time", "Side", "Fill_Price", "Qty", "Raw_Log_Note"])
        for fill in raw_fills:
            writer.writerow([
                fill.get("date", ""), fill.get("account", ""), fill.get("symbol", ""),
                fill.get("time", ""), fill.get("side", ""), fill.get("price", ""),
                fill.get("qty", ""), fill.get("note", "")
            ])

    print(f"\nOutput CSV written to: {OUTPUT_CSV}")
    print("\n--- SIGNAL SUMMARY BY DAY ---")
    for d in active_dates:
        dc = day_counts.get(d, {"buy": 0, "sell": 0})
        print(f"  {d}: {dc['buy']} BUY signals, {dc['sell']} SELL signals, {dc['buy']+dc['sell']} total")

    print(f"\nTotal signals across 3 days: {len(signals)}")
    print(f"Total raw fills from binary logs: {len(raw_fills)}")


if __name__ == "__main__":
    main()
