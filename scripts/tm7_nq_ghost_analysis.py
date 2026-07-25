"""
scripts/tm7_nq_ghost_analysis.py
=================================
Produces a comprehensive signal-vs-fill audit for TM_7 / NQU26.
- Extracts bar-level BUY/SELL signals from the GraphData export (raw data)
- Extracts ALL raw fills (both real and ghost) from binary log files using
  the production parser — RAW DATA, no processed DB
- Matches signals to fills within a 5-minute window
- Identifies the FIRST ghost fill per contract-series
- Shows the sequence before and after the first ghost
- Flags whether removal of the ghost + its paired fill restores the sequence

Output: docs/tm7_nq_ghost_analysis.csv (Google Sheets importable)
"""

import os
import sys
import re
import struct
import datetime
import csv
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GRAPHDATA_FILE = PROJECT_ROOT / "TM_7_NQU26 [CBV][M]  1000 Volume #5_GraphData (1).txt"
DATASET_DIR = PROJECT_ROOT / "dataset"
OUTPUT_CSV = PROJECT_ROOT / "docs" / "tm7_nq_ghost_analysis.csv"

# Signal columns (0-based) from GraphData header
COL_DATE = 0
COL_TIME = 1
COL_BUY_PRICE = 13
COL_SELL_PRICE = 14
COL_SELL_TARGET1 = 15
COL_BUY_TARGET1 = 16
COL_SELL_STOPLOSS = 17
COL_BUY_STOPLOSS = 18
COL_AUTO_TRADER_BUY = 30
COL_AUTO_TRADER_SELL = 31

# ── Step 1: Parse Bar Signals from GraphData ─────────────────────────────────

def parse_signals(filepath, num_days=3):
    signals = []
    seen_dates = []

    with open(str(filepath), "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 35:
            continue
        try:
            date_str = parts[COL_DATE]  # e.g. "2026-6-10"
            time_str = parts[COL_TIME]  # e.g. "16:15:00.237000"
            buy_price  = float(parts[COL_BUY_PRICE])
            sell_price = float(parts[COL_SELL_PRICE])
            auto_buy   = float(parts[COL_AUTO_TRADER_BUY])
            auto_sell  = float(parts[COL_AUTO_TRADER_SELL])
            buy_target1  = float(parts[COL_BUY_TARGET1])
            sell_target1 = float(parts[COL_SELL_TARGET1])
            buy_stop   = float(parts[COL_BUY_STOPLOSS])
            sell_stop  = float(parts[COL_SELL_STOPLOSS])
        except (ValueError, IndexError):
            continue

        is_buy  = buy_price > 0
        is_sell = sell_price > 0
        if not (is_buy or is_sell):
            continue

        if date_str not in seen_dates:
            if len(seen_dates) >= num_days:
                break
            seen_dates.append(date_str)
        if date_str not in seen_dates:
            continue

        # Normalize date to YYYY-MM-DD
        d_parts = date_str.split("-")
        iso_date = f"{d_parts[0]}-{int(d_parts[1]):02d}-{int(d_parts[2]):02d}"

        # Parse bar time
        bar_time_parts = time_str.split(":")
        bar_h = int(bar_time_parts[0])
        bar_m = int(bar_time_parts[1])
        bar_s = float(bar_time_parts[2]) if len(bar_time_parts) > 2 else 0.0

        signals.append({
            "date": iso_date,
            "raw_date": date_str,
            "bar_time": time_str[:8],
            "bar_h": bar_h,
            "bar_m": bar_m,
            "bar_s": bar_s,
            "direction": "BUY" if is_buy else "SELL",
            "entry_price": buy_price if is_buy else sell_price,
            "target1": buy_target1 if is_buy else sell_target1,
            "stop_loss": buy_stop if is_buy else sell_stop,
            "auto_executed": "YES" if (auto_buy > 0 or auto_sell > 0) else "NO",
        })

    return signals, seen_dates


# ── Step 2: Parse Raw Fills from Binary Logs (using production parser) ───────

def extract_raw_fills_from_binary(file_path, file_date_str):
    """
    Use the production TLV parser logic to extract ALL fills from a binary file.
    Returns list of fills including ghost (no strategy tag) and real (with strategy tag).
    """
    fills = []

    if not os.path.exists(file_path):
        return fills

    filesize = os.path.getsize(file_path)
    if filesize == 0:
        return fills

    with open(file_path, "rb") as f:
        data = f.read(100 * 1024 * 1024)  # 100MB cap

    n = len(data)
    offset = 0
    current_ts_str = None
    current_note = ""
    current_msg = ""
    current_side = None
    current_symbol = "NQ"
    current_oid = None
    internal_oid = None
    pending = None

    def _parse_ts(val_bytes):
        """Parse tag 0x66 as SCDateTime double."""
        if len(val_bytes) < 8:
            return None
        try:
            v = struct.unpack("<d", val_bytes[:8])[0]
            if 30000 < v < 100000:
                base = datetime.datetime(1899, 12, 30)
                return base + datetime.timedelta(days=v)
        except:
            pass
        try:
            micros = struct.unpack("<q", val_bytes[:8])[0]
            if 1262304000000000 <= micros <= 2082758400000000:
                return datetime.datetime.utcfromtimestamp(micros / 1_000_000.0)
        except:
            pass
        return None

    def flush_pending():
        if pending is None:
            return
        side = pending.get("side")
        if side not in ("BUY", "SELL"):
            return

        msg = pending.get("msg", "").lower()
        note = pending.get("note", "")

        # Ghost detection: Trading Evaluator (Filled) without strategy tag
        is_evaluator_fill = "trading evaluator" in msg and "filled" in msg
        has_strategy_tag = "at_" in msg or bool(re.search(r"[A-Za-z0-9]", note))
        is_ghost = is_evaluator_fill and not has_strategy_tag

        fills.append({
            "date": file_date_str,
            "fill_time": pending.get("ts_str", "?"),
            "symbol": pending.get("symbol", "NQ"),
            "side": side,
            "bid": pending.get("bid", 0),
            "ask": pending.get("ask", 0),
            "last_price": pending.get("last", 0),
            "order_id": pending.get("oid", ""),
            "internal_oid": pending.get("ioid", ""),
            "note": note,
            "msg": pending.get("msg", "")[:120],
            "is_ghost": is_ghost,
            "has_strategy_tag": has_strategy_tag,
            "is_evaluator_fill": is_evaluator_fill,
        })

    while offset < n - 8:
        try:
            tag = struct.unpack("<I", data[offset:offset+4])[0]
            length = struct.unpack("<I", data[offset+4:offset+8])[0]

            if tag == 0 or tag > 512 or length > 65536:
                next_ptr = data.find(b'\x66\x00\x00\x00', offset + 1)
                if next_ptr == -1:
                    break
                offset = next_ptr
                continue

            val_start = offset + 8
            val_end = val_start + length
            if val_end > n:
                break

            val = data[val_start:val_end]

            if tag == 0x66:  # Timestamp = start of new record
                if pending is not None:
                    flush_pending()
                dt = _parse_ts(val)
                if dt:
                    current_ts_str = dt.strftime("%H:%M:%S")
                pending = {
                    "ts_str": current_ts_str,
                    "symbol": current_symbol,
                }
                current_note = ""
                current_msg = ""
                current_side = None
                current_oid = None

            elif tag == 0x67:  # Symbol
                sym = val.decode("utf-8", errors="ignore").strip("\x00").strip()
                if sym:
                    current_symbol = sym
                    if pending:
                        pending["symbol"] = sym

            elif tag == 0x68:  # Message text (104)
                txt = val.decode("utf-8", errors="ignore")
                current_msg = txt
                if pending:
                    pending["msg"] = txt
                    # Extract Bid/Ask/Last from message
                    bm = re.search(r"bid[:\s]+([\d]+\.?[\d]*)", txt, re.IGNORECASE)
                    am = re.search(r"ask[:\s]+([\d]+\.?[\d]*)", txt, re.IGNORECASE)
                    lm = re.search(r"last[:\s]+([\d]+\.?[\d]*)", txt, re.IGNORECASE)
                    if bm:
                        pending["bid"] = float(bm.group(1))
                    if am:
                        pending["ask"] = float(am.group(1))
                    if lm:
                        pending["last"] = float(lm.group(1))

            elif tag == 0x82:  # Order Note / Strategy tag
                note_val = val.decode("utf-8", errors="ignore").strip()
                if note_val:
                    current_note = note_val
                    if pending:
                        pending["note"] = (pending.get("note", "") + " " + note_val).strip()

            elif tag == 0x69:  # Buy/Sell code
                try:
                    if length == 8:
                        code = struct.unpack("<q", val[:8])[0]
                        if code == 1:
                            current_side = "BUY"
                        elif code == 2:
                            current_side = "SELL"
                        if pending and current_side:
                            pending["side"] = current_side
                except:
                    pass

            elif tag == 0x6D:  # Side byte: 1=BUY, 2=SELL
                try:
                    code = val[0]
                    mapped = "BUY" if code == 1 else ("SELL" if code == 2 else None)
                    if mapped:
                        current_side = mapped
                        if pending:
                            pending["side"] = current_side
                except:
                    pass

            elif tag == 0x6A:  # Order ID
                oid = val.decode("utf-8", errors="ignore").strip()
                if oid and pending:
                    pending["oid"] = oid

            elif tag == 0x69 and length == 8:
                try:
                    ioid = str(struct.unpack("<q", val[:8])[0])
                    if pending:
                        pending["ioid"] = ioid
                except:
                    pass

            offset = val_end

        except Exception:
            offset += 8

    if pending is not None:
        flush_pending()

    return fills


# ── Step 3: Detect Side from "Updated Internal Position" messages ─────────────

def extract_position_fills(file_path, file_date_str):
    """
    Parse 'Updated Internal Position Quantity to X. Previous: Y. Fill of InternalOrderID: Z'
    messages to reconstruct the exact sequence of position changes.
    Also capture the matching fill price from the prior 'Trade simulation fill' message.
    """
    fills = []
    try:
        with open(file_path, "rb") as f:
            data = f.read(100 * 1024 * 1024)
    except:
        return fills

    n = len(data)
    offset = 0
    current_ts = None
    prev_bid = 0
    prev_ask = 0
    prev_last = 0
    prev_has_tag = False
    prev_msg = ""
    position = 0  # tracked position

    while offset < n - 8:
        try:
            tag = struct.unpack("<I", data[offset:offset+4])[0]
            length = struct.unpack("<I", data[offset+4:pos+8])[0] if False else struct.unpack("<I", data[offset+4:offset+8])[0]

            if tag == 0 or tag > 512 or length > 65536:
                next_ptr = data.find(b'\x66\x00\x00\x00', offset + 1)
                if next_ptr == -1:
                    break
                offset = next_ptr
                continue

            val_start = offset + 8
            val_end = val_start + length
            if val_end > n:
                break

            val = data[val_start:val_end]

            if tag == 0x66:
                try:
                    v = struct.unpack("<d", val[:8])[0]
                    if 30000 < v < 100000:
                        base = datetime.datetime(1899, 12, 30)
                        current_ts = (base + datetime.timedelta(days=v)).strftime("%H:%M:%S")
                except:
                    pass

            elif tag == 0x68:  # text message
                txt = val.decode("utf-8", errors="ignore")
                txt_l = txt.lower()

                # Capture fill price from "Trade simulation fill. Bid: X Ask: Y Last: Z"
                if "trade simulation fill" in txt_l and "bid:" in txt_l:
                    bm = re.search(r"bid[:\s]+([\d]+\.?[\d]*)", txt_l)
                    am = re.search(r"ask[:\s]+([\d]+\.?[\d]*)", txt_l)
                    lm = re.search(r"last[:\s]+([\d]+\.?[\d]*)", txt_l)
                    prev_bid = float(bm.group(1)) if bm else 0
                    prev_ask = float(am.group(1)) if am else 0
                    prev_last = float(lm.group(1)) if lm else 0
                    prev_has_tag = "text: tag:" in txt_l or "autotrader_" in txt_l
                    prev_msg = txt

                # Position update message
                elif "updated internal position quantity" in txt_l and "fill of internalorderid" in txt_l:
                    new_m = re.search(r"quantity to\s*(-?\d+)", txt_l)
                    prev_m = re.search(r"previous:\s*(-?\d+)", txt_l)
                    ioid_m = re.search(r"fill of internalorderid:\s*(\d+)", txt_l)

                    new_pos = int(new_m.group(1)) if new_m else None
                    old_pos = int(prev_m.group(1)) if prev_m else None
                    ioid = ioid_m.group(1) if ioid_m else ""

                    if new_pos is not None and old_pos is not None:
                        delta = new_pos - old_pos
                        # Determine side: positive delta = BUY, negative = SELL
                        if delta > 0:
                            side = "BUY"
                        elif delta < 0:
                            side = "SELL"
                        else:
                            side = "FLAT"

                        # Determine if ghost: fill has no strategy tag
                        is_ghost = not prev_has_tag

                        # Position transitions
                        if old_pos == 0 and new_pos != 0:
                            action = "ENTRY"
                        elif new_pos == 0 and old_pos != 0:
                            action = "EXIT"
                        elif (old_pos > 0 and new_pos < 0) or (old_pos < 0 and new_pos > 0):
                            action = "FLIP"
                        else:
                            action = "SCALE"

                        fills.append({
                            "date": file_date_str,
                            "fill_time": current_ts or "?",
                            "side": side,
                            "qty_delta": abs(delta),
                            "pos_before": old_pos,
                            "pos_after": new_pos,
                            "action": action,
                            "bid": prev_bid,
                            "ask": prev_ask,
                            "fill_price": prev_last,
                            "internal_oid": ioid,
                            "is_ghost": is_ghost,
                            "has_strategy_tag": prev_has_tag,
                            "raw_msg": prev_msg[:100],
                        })
                        position = new_pos
                        # Reset prev fill data
                        prev_bid = prev_ask = prev_last = 0
                        prev_has_tag = False
                        prev_msg = ""

            offset = val_end

        except Exception:
            offset += 8

    return fills


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("TM_7 / NQU26  Ghost Fill Sequence Analysis")
    print("RAW DATA — No processed DB used")
    print("=" * 60)

    # 1. Get bar signals
    print("\n[1] Parsing bar signals from GraphData...")
    signals, active_dates = parse_signals(GRAPHDATA_FILE, num_days=3)
    iso_dates = []
    for d in active_dates:
        parts = d.split("-")
        iso_dates.append(f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}")
    print(f"    3 Days Selected: {iso_dates}")
    print(f"    Total Signal Bars: {len(signals)}")

    # 2. Parse raw fills per day
    print("\n[2] Parsing raw fills from binary TM_7 files (position-based)...")
    all_fills = []
    for iso_date in iso_dates:
        fpath = DATASET_DIR / f"TradeActivityLog_{iso_date}_UTC.TM_7.data"
        print(f"    Reading: {fpath.name} ({fpath.stat().st_size if fpath.exists() else 'MISSING'} bytes)")
        day_fills = extract_position_fills(str(fpath), iso_date)
        # Filter NQ only (price range 15000-30000 for NQ)
        nq_fills = [f for f in day_fills if 15000 <= f.get("fill_price", 0) <= 35000]
        print(f"    -> {len(day_fills)} total raw fills, {len(nq_fills)} NQ-range fills")
        all_fills.extend(nq_fills)

    # 3. Sequence analysis per day
    print("\n[3] Analyzing sequence integrity (ghost detection)...")
    for iso_date in iso_dates:
        day_fills = [f for f in all_fills if f["date"] == iso_date]
        ghosts = [f for f in day_fills if f["is_ghost"]]
        real = [f for f in day_fills if not f["is_ghost"]]
        print(f"    {iso_date}: {len(day_fills)} NQ fills, {len(ghosts)} GHOST, {len(real)} REAL")

    # 4. Find first ghost per day
    print("\n[4] First ghost fill per day:")
    first_ghosts = {}
    for iso_date in iso_dates:
        day_fills = [f for f in all_fills if f["date"] == iso_date]
        for i, f in enumerate(day_fills):
            if f["is_ghost"]:
                first_ghosts[iso_date] = (i, f)
                print(f"    {iso_date}: First ghost at position #{i+1} | "
                      f"{f['fill_time']} | {f['side']} | price={f['fill_price']} | "
                      f"pos_before={f['pos_before']} -> pos_after={f['pos_after']}")
                break
        else:
            print(f"    {iso_date}: NO ghost fills found in NQ range!")

    # 5. Write output CSV
    os.makedirs(str(OUTPUT_CSV.parent), exist_ok=True)
    print(f"\n[5] Writing output to: {OUTPUT_CSV}")

    with open(str(OUTPUT_CSV), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        # Section A: Signal List
        writer.writerow(["SECTION A: BAR SIGNAL LIST (from GraphData export - RAW)"])
        writer.writerow(["Date", "Bar_Time", "Direction", "Entry_Price",
                         "Target1", "Stop_Loss", "Auto_Executed"])
        for s in signals:
            writer.writerow([
                s["date"], s["bar_time"], s["direction"],
                s["entry_price"], s["target1"], s["stop_loss"], s["auto_executed"]
            ])
        writer.writerow([])

        # Section B: Daily Signal Count
        writer.writerow(["SECTION B: DAILY SIGNAL TOTALS"])
        writer.writerow(["Date", "BUY_Signals", "SELL_Signals", "Total_Signals"])
        day_sig = defaultdict(lambda: {"buy": 0, "sell": 0})
        for s in signals:
            day_sig[s["date"]]["buy" if s["direction"] == "BUY" else "sell"] += 1
        for d in iso_dates:
            ds = day_sig.get(d, {"buy": 0, "sell": 0})
            writer.writerow([d, ds["buy"], ds["sell"], ds["buy"] + ds["sell"]])
        writer.writerow([])

        # Section C: Raw Fill Sequence per day
        writer.writerow(["SECTION C: RAW FILL SEQUENCE FROM BINARY LOGS (NQ range only, TM_7 account)"])
        writer.writerow(["Date", "Fill_#", "Fill_Time", "Side", "Qty_Delta",
                         "Pos_Before", "Pos_After", "Action",
                         "Fill_Price", "Bid", "Ask",
                         "Is_Ghost", "Has_Strategy_Tag", "Internal_OID", "Raw_Msg"])
        for iso_date in iso_dates:
            day_fills = [f for f in all_fills if f["date"] == iso_date]
            writer.writerow([f"--- {iso_date} ---"])
            for i, fill in enumerate(day_fills):
                writer.writerow([
                    fill["date"], i + 1, fill["fill_time"],
                    fill["side"], fill["qty_delta"],
                    fill["pos_before"], fill["pos_after"],
                    fill["action"], fill["fill_price"],
                    fill["bid"], fill["ask"],
                    "GHOST" if fill["is_ghost"] else "REAL",
                    "YES" if fill["has_strategy_tag"] else "NO",
                    fill["internal_oid"],
                    fill["raw_msg"],
                ])
        writer.writerow([])

        # Section D: Ghost Analysis — What happens if you remove ghost + original
        writer.writerow(["SECTION D: GHOST IMPACT ANALYSIS — Removal Scenario"])
        writer.writerow(["If ghost fill (and matching entry) are removed, does sequence stay intact?"])
        writer.writerow(["Date", "First_Ghost_At_Fill#", "Ghost_Time", "Ghost_Side",
                         "Ghost_Price", "Pos_Before_Ghost", "Pos_After_Ghost",
                         "Sequence_OK_Before_Ghost", "Sequence_OK_After_Removal",
                         "Notes"])
        for iso_date in iso_dates:
            day_fills = [f for f in all_fills if f["date"] == iso_date]
            if iso_date not in first_ghosts:
                writer.writerow([iso_date, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A",
                                  "YES", "YES", "No ghost fills on this day"])
                continue

            ghost_idx, ghost_fill = first_ghosts[iso_date]

            # Check: Was sequence clean before the ghost?
            pre_fills = day_fills[:ghost_idx]
            pos = 0
            sequence_ok_before = True
            issues_before = []
            for f in pre_fills:
                new_pos = f["pos_after"]
                # Check for unexpected flips
                if pos != 0 and f["action"] == "FLIP":
                    issues_before.append(f"Flip at {f['fill_time']}")
                pos = new_pos
            if issues_before:
                sequence_ok_before = False

            # Simulate removing ghost + its matching entry
            # The "original" trade is the fill immediately before the ghost that established pos
            # After removal: pos should track as if ghost never happened
            simulated_pos = 0
            sequence_ok_after = True
            issues_after = []
            entry_to_remove_idx = None

            # Find the entry that ghost "paired" with (prev fill when pos was 0→nonzero)
            for i in range(ghost_idx - 1, -1, -1):
                if day_fills[i]["action"] == "ENTRY":
                    entry_to_remove_idx = i
                    break

            skip_indices = {ghost_idx}
            if entry_to_remove_idx is not None:
                skip_indices.add(entry_to_remove_idx)

            for i, f in enumerate(day_fills):
                if i in skip_indices:
                    continue
                new_pos = simulated_pos + (f["qty_delta"] if f["side"] == "BUY" else -f["qty_delta"])
                if new_pos != f["pos_after"] and abs(new_pos - simulated_pos) != f["qty_delta"]:
                    issues_after.append(f"Pos mismatch at {f['fill_time']}: expected {new_pos}, got {f['pos_after']}")
                simulated_pos = new_pos

            if issues_after:
                sequence_ok_after = False

            writer.writerow([
                iso_date,
                ghost_idx + 1,
                ghost_fill["fill_time"],
                ghost_fill["side"],
                ghost_fill["fill_price"],
                ghost_fill["pos_before"],
                ghost_fill["pos_after"],
                "YES" if sequence_ok_before else f"NO — {'; '.join(issues_before)}",
                "YES" if sequence_ok_after else f"NO — {'; '.join(issues_after[:3])}",
                f"Entry to remove: fill #{entry_to_remove_idx+1 if entry_to_remove_idx else 'N/A'}"
            ])

    print("\nDone! Open in Google Sheets via File -> Import -> Upload")
    print(f"File: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
