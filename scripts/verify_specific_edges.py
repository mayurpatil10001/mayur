import sqlite3
import math
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "trading_platform.db"

def run_edge_stability_analysis(symbol, account):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get Date range
    cursor.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE symbol=? AND account_name=?", (symbol, account))
    row = cursor.fetchone()
    if not row or not row[0]:
        print(f"No data for {account} on {symbol}")
        return
    
    first_dt = datetime.fromisoformat(row[0][:10])
    last_dt = datetime.fromisoformat(row[1][:10])
    
    print(f"\n--- STABILITY ANALYSIS: {account} ({symbol}) ---")
    print(f"Range: {row[0][:10]} to {row[1][:10]}")
    
    # 1. Identify Globally Best Bins (>50 trades total)
    cursor.execute("""
        SELECT 
            printf('%02d:%02d',
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            SUM(profit_loss) as total_pnl,
            COUNT(*) as n,
            AVG(profit_loss) as avg_trade
        FROM processed_trades
        WHERE symbol = ? AND account_name = ?
        GROUP BY time_slot
        HAVING n >= 200 AND total_pnl > 0
        ORDER BY total_pnl DESC
    """, (symbol, account))
    
    best_bins = [dict(r) for r in cursor.fetchall()]
    
    if not best_bins:
        print(f"No globally persistent edges found for {account} with >200 trades.")
        return

    # 2. Check each bin across 3-month windows
    print(f"{'Slot':<5} | {'Trades':<6} | {'Total PnL':<10} | {'Max DD (Block)':<15} | {'Stability'}")
    print("-" * 70)
    
    for b in best_bins:
        slot = b["time_slot"]
        
        # Split history into 90-day blocks
        blocks_profitable = 0
        total_blocks = 0
        curr = first_dt
        worst_block_pnl = 0
        
        while curr + timedelta(days=90) <= last_dt:
            t1 = curr.strftime("%Y-%m-%d")
            t2 = (curr + timedelta(days=90)).strftime("%Y-%m-%d")
            
            cursor.execute(f"""
                SELECT SUM(profit_loss) FROM (
                    SELECT profit_loss, 
                        printf('%02d:%02d',
                            CAST(strftime('%H', entry_time) AS INTEGER),
                            CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                        ) as slot_calc
                    FROM processed_trades
                    WHERE symbol=? AND account_name=? AND entry_time >= ? AND entry_time < ?
                ) WHERE slot_calc = ?
            """, (symbol, account, t1, t2, slot))
            
            pnl = cursor.fetchone()[0] or 0
            if pnl > 0: blocks_profitable += 1
            if pnl < worst_block_pnl: worst_block_pnl = pnl
            total_blocks += 1
            curr += timedelta(days=30) # Rolling windows
            
        stability = (blocks_profitable / total_blocks * 100) if total_blocks > 0 else 0
        print(f"{slot:<5} | {b['n']:<6} | ${b['total_pnl']:>9.0f} | ${worst_block_pnl:>14.0f} | {stability:3.1f}%")

    conn.close()

if __name__ == "__main__":
    for s in ["NQ", "ES"]:
        for a in ["V_sim16", "TM_6", "TS_5"]:
            run_edge_stability_analysis(s, a)
