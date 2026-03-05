import os

# --- PATCH BINARY LOG PARSER ---
fp_binary = r'c:\SierraChart\SC results WF\trading_platform\services\binary_log_parser.py'
with open(fp_binary, 'r', encoding='utf-8') as f:
    text = f.read()

target1 = "    def _pairs_to_trades(self, fills: List[Dict], persist_state: bool = True) -> (List[Dict], int):"
repl1 = "    def _pairs_to_trades(self, fills: List[Dict], persist_state: bool = True) -> tuple[List[Dict], int, List[Dict]]:"
if target1 in text: text = text.replace(target1, repl1)

target2 = "            trades, unpaired = self._pairs_to_trades(deduped_fills, persist_state=True)"
repl2 = "            trades, unpaired, dropped_ghosts = self._pairs_to_trades(deduped_fills, persist_state=True)"
if target2 in text: text = text.replace(target2, repl2)

target3 = """        all_trades = []
        unpaired_count = 0"""
repl3 = """        all_trades = []
        unpaired_count = 0
        all_dropped_ghost_fills = []"""
if target3 in text: text = text.replace(target3, repl3)

target4 = """                buys, sells = [], []
                for f in group:
                    qty, side, price, ts = f['quantity'], f['side'], f['price'], f['timestamp']
                    ts_val = f.get('ts_val', 0)
                    
                    if side == 'BUY' or side == 'LONG':"""
                    
repl4 = """                buys, sells = [], []
                for f in group:
                    qty, side, price, ts = f['quantity'], f['side'], f['price'], f['timestamp']
                    ts_val = f.get('ts_val', 0)
                    
                    # Current net pos: positive = LONG, negative = SHORT
                    current_net = sum(b['qty'] for b in buys) - sum(s['qty'] for s in sells)
                    max_pos = 3 # Hard limit for clamping 
                    
                    # Position Clamping Validator
                    if side == 'BUY' or side == 'LONG':
                        intended_net = current_net + qty
                        if intended_net > max_pos:
                            allowed_qty = max(0, max_pos - current_net)
                            dropped_qty = qty - allowed_qty
                            if dropped_qty > 0:
                                import os
                                os.makedirs("logs", exist_ok=True)
                                with open("logs/import_clipping.log", "a") as clip_log:
                                    clip_log.write(f"[{ts}] {acc} {base_sym} | GHOST FILL BLOCKED | Side: BUY | Total Qty: {qty} | Allowed: {allowed_qty} | Dropped: {dropped_qty} | Pre-Pos: {current_net} | Limit: {max_pos}\\n")
                                all_dropped_ghost_fills.append({
                                    "timestamp": ts, "account": acc, "symbol": base_sym,
                                    "side": "BUY", "dropped_qty": dropped_qty, "pre_position": current_net, "limit": max_pos
                                })
                            qty = allowed_qty
                            if qty == 0: continue
                    else: # SELL or SHORT
                        intended_net = current_net - qty
                        if intended_net < -max_pos:
                            allowed_qty = max(0, max_pos + current_net)
                            dropped_qty = qty - allowed_qty
                            if dropped_qty > 0:
                                import os
                                os.makedirs("logs", exist_ok=True)
                                with open("logs/import_clipping.log", "a") as clip_log:
                                    clip_log.write(f"[{ts}] {acc} {base_sym} | GHOST FILL BLOCKED | Side: SELL | Total Qty: {qty} | Allowed: {allowed_qty} | Dropped: {dropped_qty} | Pre-Pos: {current_net} | Limit: {max_pos}\\n")
                                all_dropped_ghost_fills.append({
                                    "timestamp": ts, "account": acc, "symbol": base_sym,
                                    "side": "SELL", "dropped_qty": dropped_qty, "pre_position": current_net, "limit": max_pos
                                })
                            qty = allowed_qty
                            if qty == 0: continue
                            
                    if side == 'BUY' or side == 'LONG':"""
if target4 in text: text = text.replace(target4, repl4)

target5 = "        return all_trades, unpaired_count"
repl5 = "        return all_trades, unpaired_count, all_dropped_ghost_fills"
if target5 in text: text = text.replace(target5, repl5)

with open(fp_binary, 'w', encoding='utf-8') as f:
    f.write(text)


# --- PATCH TRADE IMPORT SERVICE ---
fp_trade = r'c:\SierraChart\SC results WF\trading_platform\services\trade_import_service.py'
with open(fp_trade, 'r', encoding='utf-8') as f:
    text_trade = f.read()

target_trade_call = "        trades, unpaired_count = parser._pairs_to_trades(fills)"
repl_trade_call = "        trades, unpaired_count, dropped_ghost_fills = parser._pairs_to_trades(fills)"
if target_trade_call in text_trade:
    text_trade = text_trade.replace(target_trade_call, repl_trade_call)

target_trade_result = """class ImportResult:
    new_trades: int = 0
    duplicates: int = 0
    errors: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    total_parsed: int = 0
    parsed_trades: list = field(default_factory=list)"""
repl_trade_result = """class ImportResult:
    new_trades: int = 0
    duplicates: int = 0
    errors: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    total_parsed: int = 0
    parsed_trades: list = field(default_factory=list)
    dropped_ghost_fills: list = field(default_factory=list)"""
if target_trade_result in text_trade:
    text_trade = text_trade.replace(target_trade_result, repl_trade_result)

# Attach dropped ghosts to result in Fills paste
target_trade_attach = """        result.parsed_trades = parsed_objs
        result.total_parsed = len(parsed_objs)"""
repl_trade_attach = """        result.parsed_trades = parsed_objs
        result.total_parsed = len(parsed_objs)
        result.dropped_ghost_fills = dropped_ghost_fills"""
if target_trade_attach in text_trade:
    text_trade = text_trade.replace(target_trade_attach, repl_trade_attach)

with open(fp_trade, 'w', encoding='utf-8') as f:
    f.write(text_trade)

print("SUCCESS")
