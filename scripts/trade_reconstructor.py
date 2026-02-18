
from typing import List, Dict, Optional
import datetime

class TradeReconstructor:
    def __init__(self, multiplier=1000, commission=4.20):
        self.multiplier = multiplier
        self.commission = commission
        self.open_positions = [] # List of {"price": float, "qty": int, "time": str, "side": str}
        self.closed_trades = []
        self.cumulative_pl = 0.0

    def process_fill(self, fill: Dict):
        # fill = {price, quantity, side, timestamp, symbol}
        qty = fill['quantity']
        price = fill['price']
        side = fill['side'] # BUY or SELL
        timestamp = fill['timestamp']
        
        while qty > 0:
            # Check if this fill closes an existing position
            matched = False
            if self.open_positions:
                # FIFO: Look at the first position
                # If opposite side, we close
                head = self.open_positions[0]
                if head['side'] != side:
                    # CLOSE logic
                    match_qty = min(qty, head['qty'])
                    
                    # Calculate P&L
                    entry_price = head['price']
                    exit_price = price
                    
                    if head['side'] == 'BUY': # Long Exit
                        pnl = (exit_price - entry_price) * self.multiplier * match_qty
                    else: # Short Exit
                        pnl = (entry_price - exit_price) * self.multiplier * match_qty
                    
                    self.cumulative_pl += pnl
                    
                    # Record Trade
                    self.closed_trades.append({
                        "Symbol": fill.get('symbol', 'Unknown'),
                        "Type": "Long" if head['side'] == 'BUY' else "Short",
                        "Entry DateTime": head['time'],
                        "Exit DateTime": timestamp,
                        "Entry Price": entry_price,
                        "Exit Price": exit_price,
                        "Quantity": match_qty,
                        "Profit/Loss (C)": pnl,
                        "Cumulative P/L": self.cumulative_pl
                    })
                    
                    # Update state
                    qty -= match_qty
                    head['qty'] -= match_qty
                    if head['qty'] == 0:
                        self.open_positions.pop(0)
                    
                    matched = True
            
            if not matched:
                # OPEN logic (Add to inventory)
                self.open_positions.append({
                    "price": price,
                    "qty": qty,
                    "time": timestamp,
                    "side": side
                })
                qty = 0 # All consumed

    def get_report(self):
        return self.closed_trades

