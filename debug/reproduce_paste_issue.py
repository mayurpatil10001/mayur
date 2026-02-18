
from datetime import datetime
import re

# Logic from TradeImportService

def _split_lines(raw_text):
    return [l for l in raw_text.replace('\r\n', '\n').split('\n') if l.strip()]

def _strip_header(lines):
    if not lines:
        return lines, None
    first_fields = lines[0].split('\t')
    if first_fields[0].strip().lower() == "symbol":
        return lines[1:], lines[0]
    return lines, None

def _get_column_map(header_row):
    mapping = {
        "symbol": 0,
        "trade_type": 1,
        "entry_datetime": 2,
        "entry_price": 3,
        "exit_datetime": 4,
        "exit_price": 5,
        "quantity": 6,
        "profit_loss": 9,
        "commission": 11,
        "note": 13,
        "duration": 25,
    }

    if not header_row:
        return mapping

    header_fields = [f.strip().lower() for f in header_row.split('\t')]
    
    def find_idx(patterns):
        for i, field in enumerate(header_fields):
            for p in patterns:
                if p in field:
                    return i
        return None

    new_mapping = {}
    new_mapping["symbol"] = find_idx(["symbol"])
    new_mapping["trade_type"] = find_idx(["trade type"])
    new_mapping["entry_datetime"] = find_idx(["entry datetime"])
    new_mapping["exit_datetime"] = find_idx(["exit datetime"])
    new_mapping["entry_price"] = find_idx(["entry price"])
    new_mapping["exit_price"] = find_idx(["exit price"])
    new_mapping["quantity"] = find_idx(["trade quantity", "quantity"])
    new_mapping["profit_loss"] = find_idx(["profit/loss (c)", "profit/loss", "p/l"])
    new_mapping["commission"] = find_idx(["commission (c)", "commission"])
    new_mapping["note"] = find_idx(["note"])
    new_mapping["duration"] = find_idx(["duration"])
    new_mapping["account"] = find_idx(["account"]) 

    # Merge
    for key, val in new_mapping.items():
        if val is not None:
            mapping[key] = val
            
    return mapping

def _parse_dt(value):
    v = value.strip()
    if not v: return None
    v = v.replace(" BP", "").replace(" EP", "").strip()
    while "  " in v: v = v.replace("  ", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None

def _parse_float(value):
    v = value.strip()
    if not v: return 0.0
    if v.endswith(" F"): v = v[:-2]
    v = v.replace("%", "").replace(",", "")
    return float(v)

def _parse_int(value):
    v = value.strip()
    if not v: return 0
    if v.endswith(" F"): v = v[:-2]
    v = v.replace("%", "")
    return int(float(v))

def parse_line(line, col_map):
    fields = line.split('\t')
    max_idx = max(col_map.values())
    
    def get_field(key):
        idx = col_map.get(key)
        return fields[idx].strip() if idx is not None and idx < len(fields) else ""

    entry_dt = _parse_dt(get_field("entry_datetime"))
    
    if entry_dt is None:
         print(f"FAILED DT: {get_field('entry_datetime')}")
    
    return {
        "symbol": get_field("symbol"),
        "entry": entry_dt,
        "pl": _parse_float(get_field("profit_loss")),
        "acc": get_field("account")
    }

raw_text = """Symbol	Trade Type	Entry DateTime	Exit DateTime	Entry Price	Exit Price	Trade Quantity	Max Open Quantity	Max Closed Quantity	Profit/Loss (C)	Cumulative Profit/Loss (C)	Duration	Commission (C)	High Price While Open	Low Price While Open	Exit Efficiency	Account	Entry Efficiency	FlatToFlat Profit/Loss (C)	FlatToFlat Max Open Profit (C)	FlatToFlat Max Open Loss (C)	Max Open Profit (C)	Max Open Loss (C)	Note	Total Efficiency	Open Position Quantity	Close Position Quantity	Highest Cumulative P/L (C)	Lowest Cumulative P/L (C)	Maximum Runup (C)	Maximum Drawdown (C)
CLF25	Short	2024-11-19  10:40:43.000	2024-11-19  10:42:33.000 EP	69.26	69.16	2	3	3	191.60	-5595.00	00:01:50	8.40	69.26	69.04	29.9%	3Q_sim14	100.0%	387.40 F	640.00	-0.01	440.00	-0.01	AutoTrader_	29.9%	3	0	0.00	-8296.80	3634.80	-8296.80
CLF25	Long	2024-11-19  10:42:37.000 BP	2024-11-19  10:44:37.000	69.17	69.37	1	3	1	195.80	-5399.20	00:02:00	4.20	69.37	69.16	98.0%	3Q_sim14	100.0%	195.80	200.00	-10.00	200.00	-10.00	AutoTrader_	93.2%	3	2	0.00	-8296.80	3634.80	-8296.80
"""

lines = _split_lines(raw_text)
lines, header = _strip_header(lines)
col_map = _get_column_map(header)
print("Parsing...")
for l in lines:
    try:
        t = parse_line(l, col_map)
        print(t)
    except Exception as e:
        print(f"Error: {e}")
