import re

with open(r'c:\SierraChart\SC results WF\trading_platform\services\trade_import_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the start of _import_activity_log
start_idx = -1
for i, line in enumerate(lines):
    if line.startswith('    def _import_activity_log(self, text: str) -> ImportResult:'):
        start_idx = i
        break

if start_idx == -1:
    print("Could not find method start")
    exit(1)

# Find the end of the method
end_idx = -1
for i in range(start_idx + 1, len(lines)):
    # method ends when indent returns to 4 spaces, e.g. def _get_column_map...
    if lines[i].startswith('    ') and not lines[i].startswith('        ') and lines[i].strip() != '':
        # wait, the next method is @staticmethod def _split_lines or something at indent 4
        # let's just find the next '    def ' or '    @staticmethod'
        if lines[i].startswith('    def ') or lines[i].startswith('    @staticmethod') or lines[i].startswith('    # ──'):
            end_idx = i
            break

if end_idx == -1:
    print("Could not find method end")
    exit(1)

print(f"Replacing lines {start_idx} to {end_idx - 1}")

new_method = """    def _import_activity_log(self, text: str) -> ImportResult:
        \"\"\"Special handler for raw Activity Log (Fills) paste.\"\"\"
        from .binary_log_parser import BinaryLogParser
        import re
        from datetime import datetime
        
        parser = BinaryLogParser(self.db_path)
        
        result = ImportResult()
        fills = []
        lines_text = [l for l in text.replace('\\r\\n', '\\n').split('\\n') if l.strip()]
        if not lines_text:
            return result
            
        header_fields = [f.strip().lower() for f in lines_text[0].split('\\t')]
        has_header = "datetime" in header_fields or "tradeaccount" in header_fields or "fillprice" in header_fields
        data_lines = lines_text[1:] if has_header else lines_text
        
        if not has_header:
            header_fields = ["activitytype", "datetime", "unknown", "ordertype", "quantity", "orderstatus", "tradeaccount", "buysell", "price", "price2", "fillprice", "filledquan", "note"]
            
        def find_idx(patterns):
            for i, field in enumerate(header_fields):
                for p in patterns:
                    if p in field: return i
            return None
            
        col_map = {
            "datetime": find_idx(["datetime", "time"]),
            "account": find_idx(["tradeaccount", "account"]),
            "side": find_idx(["buysell", "side", "type"]),
            "fillprice": find_idx(["fillprice", "price"]),
            "filledquan": find_idx(["filledquan", "quantity", "qty"]),
            "note": find_idx(["note"])
        }
        
        for idx, line in enumerate(data_lines):
            parts = line.split('\\t')
            if len(parts) < 3: continue
            
            try:
                def get_field(key): return parts[col_map[key]].strip() if col_map.get(key) is not None and col_map[key] < len(parts) else ""
                
                if parts[0].strip() != "Fills" and "Fills" not in parts[0]: continue
                
                dt_str = get_field("datetime")
                acc = get_field("account")
                side = get_field("side").upper()
                price_str = get_field("fillprice")
                qty_str = get_field("filledquan")
                note_str = get_field("note")
                
                if not dt_str or not side or not price_str or not qty_str: continue
                
                try: 
                    price = float(price_str)
                    qty = int(float(qty_str))
                except ValueError: 
                    continue
                if qty <= 0: continue
                
                symbol = "UNKNOWN"
                sym_match = re.search(r'\\b([A-Z]+[HMUZ]\\d{1,2})\\b', note_str)
                if sym_match: 
                    symbol = sym_match.group(1)
                else:
                    at_match = re.search(r'AT_([A-Z]+)', note_str)
                    if at_match: symbol = at_match.group(1)
                        
                ts_val = 0
                parsed_dt = None
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        parsed_dt = datetime.strptime(dt_str, fmt)
                        ts_val = parsed_dt.timestamp()
                        break
                    except ValueError: continue
                if not parsed_dt: continue
                    
                fills.append({
                    "timestamp": parsed_dt.isoformat(), "ts_val": ts_val, "account_name": acc, "side": side,
                    "price": price, "quantity": qty, "symbol": symbol, "order_id": "PASTE", "source": "PASTE", "offset": idx
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to parse Fills line {idx}: {e}")

        fills.sort(key=lambda x: (x['timestamp'], x['offset']))
        
        trades, unpaired_count = parser._pairs_to_trades(fills)
        
        if unpaired_count > 0:
            result.stats['unpaired'] = {
                "count": unpaired_count,
                "commission_impact": round(unpaired_count * 2.10, 2)
            }
        
        parsed_objs = []
        for t in trades:
            try:
                pt = ParsedTrade(
                    symbol=t['symbol'],
                    trade_type=t['side'],
                    entry_datetime=datetime.fromisoformat(t['entry_time']) if isinstance(t['entry_time'], str) else t['entry_time'],
                    entry_price=t['entry_price'],
                    exit_datetime=datetime.fromisoformat(t['exit_time']) if isinstance(t['exit_time'], str) else t['exit_time'],
                    exit_price=t['exit_price'],
                    quantity=t['quantity'],
                    max_open_quantity=0, max_closed_quantity=0,
                    profit_loss=t['profit_loss'],
                    cumulative_pnl=0,
                    commission=t['commission'],
                    flat_to_flat_pnl=0,
                    note=t['account'],
                    flat_to_flat_max_profit=0, flat_to_flat_max_loss=0,
                    max_open_profit=0, max_open_loss=0,
                    entry_efficiency="", exit_efficiency="", total_efficiency="",
                    high_while_open=0, low_while_open=0,
                    open_position_quantity=0, close_position_quantity=0,
                    duration="",
                    account_name=t['account'],
                    base_symbol=t['symbol']
                )
                parsed_objs.append(pt)
            except Exception as e:
                result.errors.append(f"Conversion error: {e}")

        result.parsed_trades = parsed_objs
        result.total_parsed = len(parsed_objs)
        
        conn = sqlite3.connect(self.db_path)
        touched = set()
        try:
            for pt in parsed_objs:
                touched.add(pt.account_name)
                # Ensure _is_duplicate is accessible via self
                if self._is_duplicate(conn, pt):
                    result.duplicates += 1
                else:
                    self._insert_trade(conn, pt)
                    result.new_trades += 1
            conn.commit()
            
            full_stats = {}
            for acc in touched:
                breakdown = parser.purge_anomalies(account=acc, purge_overnight=True)
                full_stats.update(breakdown)
            result.stats.update(full_stats)
            
        finally:
            conn.close()
            
        return result
"""

new_lines = lines[:start_idx] + [new_method + "\n\n"] + lines[end_idx:]

with open(r'c:\SierraChart\SC results WF\trading_platform\services\trade_import_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("SUCCESS REPLACEMENT")
