import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
import glob
import argparse
import os

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro, _scan_position_fill_order

def fmt_ts(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if d else ""

def generate_report(binary_file_glob, account_filter, symbol_filter, start_bounds, end_bounds):
    print(f"Loading binary files matching: {binary_file_glob}")
    print(f"Filtering for Account: {account_filter}, Symbol: {symbol_filter}")
    
    files = sorted(glob.glob(binary_file_glob))
    
    # Parse all fills for the account from all matching files
    fills_all_raw = []
    for fp in files:
        fp_fills, _ = _parse_file_nitro(fp, acc_filter=[account_filter, account_filter.upper()])
        fills_all_raw.extend(fp_fills)
    
    # RULE 5: Contract Isolation (Filter by Symbol)
    fills_all = [f for f in fills_all_raw if f.get('symbol') == symbol_filter]
    
    def custom_dedup(fills_list):
        # RULE 4: Millisecond-Precise Deduplication (500ms bucket)
        out = []
        seen_keys = set()
        for f in fills_list:
            ts_val = f.get('ts_val', 0)
            # Use 500ms bucket to match Rule 4
            ts_bucket = round(ts_val * 2) / 2.0
            msg_hash = hash(f.get('msgtxt', ''))
            instance_path = os.path.dirname(f.get('file_path', 'default'))
            key = (instance_path, f.get('account_name'), f.get('symbol'), f.get('side'), f.get('price'), f.get('quantity'), ts_bucket, msg_hash)
            
            if key not in seen_keys:
                out.append(f)
                seen_keys.add(key)
        return out
        
    fills_all = custom_dedup(fills_all)
    print(f"Loaded {len(fills_all)} total raw deduplicated fills for {symbol_filter}.")
    
    # Sort fills chronologically
    final_fills_all = []
    for f in fills_all:
        ts = f.get("timestamp") or f.get("trans_timestamp") or ""
        try:
            if "Z" in ts:
                d_ny = dt.datetime.fromisoformat(ts.replace("Z", ""))
            else:
                d_ny = dt.datetime.fromisoformat(ts)
            f["_dt"] = d_ny
        except:
            f["_dt"] = dt.datetime(1970,1,1)
            
        if start_bounds <= f["_dt"] <= end_bounds:
            final_fills_all.append(f)
            
    final_fills_all.sort(key=lambda x: (x["_dt"], x.get('_record_index', 0)))
    fills_all = final_fills_all
    
    print(f"Fills after time boundary filtering: {len(fills_all)}")

    if not fills_all:
        print("No fills found for the specified criteria.")
        return

    # Pair trades internally (FIFO) - Using the patched BinaryLogParser logic
    parser = BinaryLogParser(db_path=":memory:")
    # We pass fills_all which contains ghosts. parser._pairs_to_trades skip ghosts.
    raw_trades, unpaired_count, position_warnings = parser._pairs_to_trades(fills_all, persist_state=False)
    
    # Create mapping of FIFO trades
    fifo_used_fills = set()
    fill_fifo_map = {}
    
    for i, t in enumerate(raw_trades):
        fifo_id = f"FIFO_{i+1}"
        e = dt.datetime.fromisoformat(t["entry_time"])
        if e.tzinfo: e = e.replace(tzinfo=None)
        
        for f_idx, f in enumerate(fills_all):
            if f_idx in fifo_used_fills: continue
            if f["_dt"] == e and f.get('price') == t['entry_price']:
                fifo_used_fills.add(f_idx)
                fill_fifo_map.setdefault(f_idx, []).append(f"{fifo_id}_ENTRY({t['quantity']})")
                break
                
        x = dt.datetime.fromisoformat(t["exit_time"])
        if x.tzinfo: x = x.replace(tzinfo=None)
        
        for f_idx, f in enumerate(fills_all):
            if f_idx in fifo_used_fills: continue
            if f["_dt"] == x and f.get('price') == t['exit_price']:
                fifo_used_fills.add(f_idx)
                fill_fifo_map.setdefault(f_idx, []).append(f"{fifo_id}_EXIT({t['quantity']})")
                break

    # Build report output
    out = []
    out.append("=================================================================================================================================================")
    out.append("TRADE SEQUENCE ALIGNMENT REPORT (PURE BINARY EXPORT)")
    out.append(f"Account: {account_filter} | Symbol: {symbol_filter}")
    out.append(f"Time Range: {start_bounds} to {end_bounds}")
    out.append("=================================================================================================================================================")
    out.append(f"{'Time':<28} | {'Side':<5} | {'Type':<6} | {'Qty':<4} | {'Price':<8} | {'Internal FIFO Pair Map':<35} | {'Pos':<10} | {'Ghost'}")
    out.append("-" * 145)

    running_pos = 0
    from trading_platform.services.binary_log_parser import _session_trade_date_ny
    last_session_date = None

    for idx, f in enumerate(fills_all):
        is_ghost = f.get('suggests_ghost', False)
        
        # RULE 9: Session reset logic for display
        current_session_date = _session_trade_date_ny(f["_dt"])
        if last_session_date is not None and current_session_date != last_session_date:
            out.append(f"[SESSION RESET AT {f['_dt'].strftime('%H:%M:%S')}]" + "=" * 120)
            running_pos = 0
        last_session_date = current_session_date

        if is_ghost:
            ghost_flag = "Yes"
            t_type = "GHOST"
            qty = f.get('quantity', 0)
            # Ghosts don't impact position
            pos_label = running_pos
        else:
            ghost_flag = "No"
            qty = f.get('quantity', 0)
            side = f.get('side', '').upper()
            if side == "BUY":
                if running_pos >= 0:
                    t_type = "OPEN"
                else: 
                    t_type = "CLOSE" if qty <= abs(running_pos) else "CL/OP"
                running_pos += qty
            elif side == "SELL":
                if running_pos <= 0:
                    t_type = "OPEN"
                else: 
                    t_type = "CLOSE" if qty <= running_pos else "CL/OP"
                running_pos -= qty
            pos_label = running_pos
        
        side_str = f.get('side', '').upper()
        price_str = f"{f.get('price', 0):.2f}"
        qty_str = str(f.get('quantity', 0))
        t_str = fmt_ts(f['_dt'])
        
        fifo_map = ", ".join(fill_fifo_map.get(idx, []))

        out.append(f"{t_str:<28} | {side_str:<5} | {t_type:<6} | {qty_str:<4} | {price_str:<8} | {fifo_map:<35} | {pos_label:<10} | {ghost_flag}")

        # Separator when position returns to zero
        if not is_ghost and running_pos == 0:
            out.append("-" * 145)

    out.append("-" * 145)
    out.append(f"Total Internal Trades Formed: {len(raw_trades)}")
    out.append(f"Unpaired Contracts: {unpaired_count}")

    out_file = Path(__file__).resolve().parent / "trade_sequence_report.txt"
    with out_file.open("w") as f:
        f.write("\n".join(out) + "\n")
        
    print(f"Report saved to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Trade Sequence Report from pure binary files.")
    parser.add_argument("--glob", required=True, help="Glob pattern for binary files")
    parser.add_argument("--account", required=True, help="Account name filter")
    parser.add_argument("--symbol", required=True, help="Symbol/Contract filter (e.g. NQH26)")
    parser.add_argument("--start", required=True, help="Start time (ISO)")
    parser.add_argument("--end", required=True, help="End time (ISO)")

    args = parser.parse_args()
    generate_report(args.glob, args.account, args.symbol, dt.datetime.fromisoformat(args.start), dt.datetime.fromisoformat(args.end))
