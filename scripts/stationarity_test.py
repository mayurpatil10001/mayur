import sqlite3
import math
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "trading_platform.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_stationarity_test(symbol="NQ"):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE symbol=?", (symbol,))
    row = cursor.fetchone()
    if not row or not row[0]: return
    first_dt, last_dt = datetime.fromisoformat(row[0][:10]), datetime.fromisoformat(row[1][:10])
    
    print(f"\n--- STATIONARITY TEST: {symbol} ---")
    
    # 1. THE "STATIC" APPROACH (User's question)
    # Train on the FIRST 12 MONTHS, test on the REMAINING time.
    split_date = (first_dt + timedelta(days=365)).strftime("%Y-%m-%d")
    
    # Get the "Best Matrix" from the first year
    cursor.execute("""
        WITH perf AS (
            SELECT account_name,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                AVG(profit_loss) as avg_pnl, COUNT(*) as n
            FROM processed_trades WHERE symbol=? AND entry_time < ?
            GROUP BY account_name, time_slot, day_of_week HAVING n >= 30
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY time_slot, day_of_week ORDER BY avg_pnl DESC) as rn
            FROM perf
        )
        SELECT time_slot, day_of_week, account_name FROM ranked WHERE rn = 1
    """, (symbol, split_date))
    static_matrix = {(r["time_slot"], r["day_of_week"]): r["account_name"] for r in cursor.fetchall()}
    
    # Test on the rest of the history
    cursor.execute("""
        SELECT profit_loss, 
            printf('%02d:%02d',
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
        FROM processed_trades WHERE symbol=? AND entry_time >= ?
    """, (symbol, split_date))
    static_pnls = [r["profit_loss"] for r in cursor.fetchall() if static_matrix.get((r["time_slot"], r["day_of_week"])) is not None]
    
    # 2. THE "DYNAMIC" APPROACH (Walk-forward 90d/21d)
    # (Simplified: we'll use a 90d rolling and test consistently)
    dynamic_pnls = []
    curr = first_dt + timedelta(days=90)
    while curr + timedelta(days=30) <= last_dt:
        train_start = (curr - timedelta(days=90)).strftime("%Y-%m-%d")
        train_end = curr.strftime("%Y-%m-%d")
        test_start = train_end
        test_end = (curr + timedelta(days=30)).strftime("%Y-%m-%d")
        
        cursor.execute("""
            WITH perf AS (
                SELECT account_name,
                    printf('%02d:%02d',
                        CAST(strftime('%H', entry_time) AS INTEGER),
                        CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                    ) as time_slot,
                    CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                    AVG(profit_loss) as avg_pnl, COUNT(*) as n
                FROM processed_trades WHERE symbol=? AND entry_time >= ? AND entry_time < ?
                GROUP BY account_name, time_slot, day_of_week HAVING n >= 10
            ),
            ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY time_slot, day_of_week ORDER BY avg_pnl DESC) as rn
                FROM perf
            )
            SELECT time_slot, day_of_week, account_name FROM ranked WHERE rn = 1
        """, (symbol, train_start, train_end))
        m = {(r["time_slot"], r["day_of_week"]): r["account_name"] for r in cursor.fetchall()}
        
        cursor.execute("""
             SELECT account_name, profit_loss,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
            FROM processed_trades WHERE symbol=? AND entry_time>=? AND entry_time<?
        """, (symbol, test_start, test_end))
        for r in cursor.fetchall():
            if m.get((r["time_slot"], r["day_of_week"])) == r["account_name"]:
                dynamic_pnls.append(r["profit_loss"])
        curr += timedelta(days=30)

    # OUTPUT RESULTS
    def stats(pnls):
        if not pnls: return "N/A"
        total = sum(pnls)
        mean = total/len(pnls)
        std = math.sqrt(sum((x-mean)**2 for x in pnls)/max(1, len(pnls)-1))
        sharpe = (mean/std * math.sqrt(1000)) if std > 0 else 0
        return f"${total:,.0f} (Sharpe: {sharpe:.2f}, Trades: {len(pnls)})"

    print(f"STATIC (Hold year-1 best): {stats(static_pnls)}")
    print(f"DYNAMIC (Monthly refresh): {stats(dynamic_pnls)}")
    conn.close()

if __name__ == "__main__":
    for s in ["NQ", "ES", "CL"]:
        run_stationarity_test(s)
