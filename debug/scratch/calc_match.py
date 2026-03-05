import sys
import datetime as dt
import glob
sys.path.insert(0, 'C:/SierraChart/SC results WF')

from tests.test_binary_benchmark_1218 import _load_trade_list_struct, _match_trade
from trading_platform.services.binary_log_parser import BinaryLogParser, _scan_position_fill_order
from tests.test_binary_benchmark_1218 import _load_binary_fills_for_ny_1218, REF_TRADES, BINARY_GLOB_2D
from zoneinfo import ZoneInfo

def calculate_match_percentage():
    # 1. Load Truth Trades
    trade_rows = _load_trade_list_struct(REF_TRADES)
    
    # 2. Get Fills
    fills_all = _load_binary_fills_for_ny_1218(use_trans_time=False, include_ghost=True)
    
    position_order_list = []
    for fp in sorted(glob.glob(BINARY_GLOB_2D)):
        position_order_list.extend(_scan_position_fill_order(fp))
    position_map = {oid: i for i, oid in enumerate(position_order_list)}
    
    def custom_dedup(fills_list):
        out = []
        for f in fills_list:
            io = str(f.get("internal_order_id", ""))
            has_pos = io in position_map
            if not has_pos:
                ts_val = f.get('ts_val', 0)
                is_duplicate = False
                for existing in out:
                    if abs(existing.get('ts_val', 0) - ts_val) < 1.0:
                        if existing.get('side') == f.get('side') and existing.get('price') == f.get('price') and existing.get('quantity') == f.get('quantity'):
                            is_duplicate = True
                            break
                if is_duplicate:
                    continue
            out.append(f)
        return out
        
    fills_all = custom_dedup(fills_all)
    
    # Time Filter
    final_fills_all = []
    start_bounds = dt.datetime(2025, 12, 17, 17, 59, 30)
    end_bounds = dt.datetime(2025, 12, 18, 17, 30, 0)
    for f in fills_all:
        ts = f.get("timestamp") or f.get("trans_timestamp") or ""
        try:
            d_ny = dt.datetime.fromisoformat(ts.replace("Z", ""))
            f["_dt"] = d_ny
        except:
            f["_dt"] = dt.datetime(1970,1,1)
            
        if start_bounds <= f["_dt"] <= end_bounds:
            final_fills_all.append(f)
            
    final_fills_all.sort(key=lambda x: x["_dt"])
    fills_all = final_fills_all
    
    # Run Parser with Sync State
    parser = BinaryLogParser(db_path=":memory:")
    parser._pairs_to_trades(fills_all, persist_state=False)
    
    # Get Clean Fills
    fills_clean = [f for f in fills_all if not f.get('suggests_ghost')]
    
    # Generate FIFO pair trades
    fifo_trades, _, _ = parser._pairs_to_trades(fills_clean, persist_state=False)
    
    normalized_fifo = []
    for t in fifo_trades:
        side = "Long" if (t.get("side") or "").upper() == "LONG" else "Short"
        normalized_fifo.append(
            {
                "entry_dt": dt.datetime.fromisoformat(t["entry_time"]),
                "exit_dt": dt.datetime.fromisoformat(t["exit_time"]),
                "entry_price": float(t["entry_price"]),
                "exit_price": float(t["exit_price"]),
                "qty": int(t["quantity"]),
                "side": side,
            }
        )

    # Calculate match percentage
    strict_match_count = sum(1 for bt in normalized_fifo if any(_match_trade(bt, sc) for sc in trade_rows))
    strict_match_pct = (strict_match_count / len(normalized_fifo) * 100.0) if normalized_fifo else 0.0
    
    print(f"Total Sierra Chart Standard Trades (Ground Truth): {len(trade_rows)}")
    print(f"Total FIFO Engine Processed Trades: {len(normalized_fifo)}")
    print(f"Strict Identical Exact Matches: {strict_match_count}")
    print(f"Overall Benchmark Strict Match Rate: {strict_match_pct:.2f}%")

if __name__ == '__main__':
    calculate_match_percentage()
