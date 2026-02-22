import sqlite3
import math
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "trading_platform.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_persistence_test(symbol="NQ"):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get Date range
    cursor.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE symbol=?", (symbol,))
    first, last = cursor.fetchone()
    first_dt = datetime.fromisoformat(first[:10])
    last_dt = datetime.fromisoformat(last[:10])
    
    # 1. SPLIT DATA: Train on 12 months, Test on the rest
    split_date = (first_dt + timedelta(days=365)).strftime("%Y-%m-%d")
    
    print(f"\n===== LONG-TERM PERSISTENCE TEST: {symbol} =====")
    print(f"Training on first year (up to {split_date}) to find the 'Proven Edges'")
    
    # Find combinations of (account, time_slot) that have > 100 trades and TOP PNL
    # Time slot is 'HH:MM' (30 min bins)
    cursor.execute("""
        SELECT account_name,
            printf('%02d:%02d',
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            SUM(profit_loss) as total_pnl,
            COUNT(*) as n,
            SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as wr,
            AVG(profit_loss) as avg_trade,
            AVG(profit_loss*profit_loss) - (AVG(profit_loss)*AVG(profit_loss)) as var
        FROM processed_trades
        WHERE symbol = ? AND entry_time < ?
        GROUP BY account_name, time_slot
        HAVING n >= 50 AND total_pnl > 10000
        ORDER BY total_pnl DESC
    """, (symbol, split_date))
    
    proven_edges = []
    for r in cursor.fetchall():
        sd = math.sqrt(max(1.0, r["var"]))
        sharpe = (r["avg_trade"] / sd * math.sqrt(252)) if sd > 0 else 0
        proven_edges.append({
            "account": r["account_name"],
            "time_slot": r["time_slot"],
            "train_pnl": r["total_pnl"],
            "train_trades": r["n"],
            "train_sharpe": sharpe
        })
    
    print(f"Found {len(proven_edges)} proven combinations in the first year.")
    if not proven_edges:
        print("No high-conviction edges found in Year 1. Loosening filters...")
        # (Recursive retry or looser logic here if needed)
        conn.close()
        return

    # 2. FORWARD TEST: How did these specific combinations perform in Year 2?
    print(f"\nTOP EDGES FROM YEAR 1 AND THEIR PERFORMANCE IN YEAR 2:")
    print(f"{'Account':<15} | {'Slot':<5} | {'Y1 PnL':<10} | {'Y2 PnL':<10} | {'Result'}")
    print("-" * 65)
    
    total_y2_pnl = 0
    consistent_edges = 0
    
    for edge in proven_edges[:20]: # Show top 20
        cursor.execute("""
            SELECT SUM(profit_loss), COUNT(*) 
            FROM processed_trades 
            WHERE symbol = ? AND account_name = ? AND entry_time >= ?
            AND printf('%02d:%02d',
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) = ?
        """, (symbol, edge["account"], split_date, edge["time_slot"]))
        y2_pnl, y2_n = cursor.fetchone()
        
        y2_pnl = float(y2_pnl or 0)
        y2_n = int(y2_n or 0)
        
        status = "WINNER" if y2_pnl > 0 else "DECAYED"
        if status == "WINNER": consistent_edges += 1
        total_y2_pnl += y2_pnl
        
        print(f"{edge['account']:<15} | {edge['time_slot']:<5} | ${edge['train_pnl']:>8.0f} | ${y2_pnl:>8.0f} | {status}")

    print("-" * 65)
    print(f"Global Year 2 Result for these Edges: ${total_y2_pnl:,.2f}")
    print(f"Consistency: {consistent_edges}/{min(len(proven_edges), 20)} edges stayed profitable.")
    
    conn.close()

if __name__ == "__main__":
    for s in ["NQ", "ES"]:
        run_persistence_test(s)
