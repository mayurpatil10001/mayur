import sqlite3
import math
from datetime import datetime, timedelta
from collections import defaultdict
import json

DB_PATH = "trading_platform.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def build_matrix_classic(cursor, symbol, start_date, end_date, min_trades=10, min_pnl=12, min_wr=45):
    """Simple Avg PnL ranking."""
    cursor.execute(f"""
        WITH perf AS (
            SELECT account_name,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as n,
                AVG(profit_loss) as avg_pnl,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as wr
            FROM processed_trades
            WHERE symbol = ? AND entry_time >= ? AND entry_time < ?
            GROUP BY account_name, time_slot, day_of_week
            HAVING n >= ? AND avg_pnl > ? AND wr >= ?
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY time_slot, day_of_week ORDER BY avg_pnl DESC) as rn
            FROM perf
        )
        SELECT time_slot, day_of_week, account_name FROM ranked WHERE rn = 1
    """, (symbol, start_date, end_date, min_trades, min_pnl, min_wr))
    return {(r["time_slot"], r["day_of_week"]): r["account_name"] for r in cursor.fetchall()}

def build_matrix_ensemble(cursor, symbol, start_date, end_date, min_trades=10, min_pnl=12, min_wr=45):
    """Consensus 2.0 ranking logic."""
    end_dt = datetime.fromisoformat(end_date)
    start_dt = datetime.fromisoformat(start_date)
    total_days = (end_dt - start_dt).days
    windows = [total_days, total_days // 2, total_days // 3]
    window_results = []
    
    for w_days in windows:
        if w_days < 10: continue
        w_start = end_dt - timedelta(days=w_days)
        w_start_str = w_start.strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT account_name,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as n,
                AVG(profit_loss) as avg_pnl,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as wr,
                AVG(profit_loss * profit_loss) - (AVG(profit_loss) * AVG(profit_loss)) as variance
            FROM processed_trades
            WHERE symbol = ? AND entry_time >= ? AND entry_time < ?
            GROUP BY account_name, time_slot, day_of_week
            HAVING n >= ?
        """, (symbol, w_start_str, end_date, max(3, int(min_trades * w_days / total_days))))
        
        w_candidates = {}
        for r in cursor.fetchall():
            key = (r["time_slot"], r["day_of_week"])
            std_dev = math.sqrt(max(1.0, r["variance"]))
            sharpe = r["avg_pnl"] / (std_dev / 10.0) if std_dev > 0 else 0
            score = (min(2.0, r["avg_pnl"] / 25.0) * 0.6) + (min(2.0, sharpe / 4.0) * 0.4)
            if r["avg_pnl"] < min_pnl or r["wr"] < min_wr: score *= 0.1
            if key not in w_candidates or score > w_candidates[key]["score"]:
                w_candidates[key] = {"account": r["account_name"], "score": score}
        window_results.append(w_candidates)
    
    final_matrix = {}
    all_keys = set()
    for res in window_results: all_keys.update(res.keys())
    for key in all_keys:
        votes = defaultdict(float)
        for i, res in enumerate(window_results):
            if key in res:
                weight = 1.0 if i == 0 else 0.7
                votes[res[key]["account"]] += res[key]["score"] * weight
        if votes:
            best = max(votes, key=votes.get)
            if votes[best] > 0.8: final_matrix[key] = best
    return final_matrix

def apply_oos(cursor, matrix, symbol, start_date, end_date):
    if not matrix: return []
    cursor.execute("""
        SELECT account_name, profit_loss, entry_time,
            printf('%02d:%02d',
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
        FROM processed_trades
        WHERE symbol = ? AND entry_time >= ? AND entry_time < ?
    """, (symbol, start_date, end_date))
    pnls = []
    for r in cursor.fetchall():
        key = (r["time_slot"], r["day_of_week"])
        if matrix.get(key) == r["account_name"]:
            pnls.append(float(r["profit_loss"]))
    return pnls

def calculate_sharpe(pnls):
    if not pnls or len(pnls) < 2: return 0.0
    mean = sum(pnls) / len(pnls)
    std = math.sqrt(sum((x - mean)**2 for x in pnls) / (len(pnls) - 1))
    if std == 0: return 0.0
    # Approx annualized: (avg trade / std trade) * sqrt(trades per year)
    # Assuming 1000 trades/year for NQ average
    return (mean / std) * math.sqrt(1000)

def build_matrix_statistical(cursor, symbol, start_date, end_date, min_trades=10, min_pnl=12, min_wr=45):
    """CWEV (Expected Value) ranking logic."""
    cursor.execute(f"""
        WITH perf AS (
            SELECT account_name,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as n,
                AVG(profit_loss) as avg_pnl,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as wr
            FROM processed_trades
            WHERE symbol = ? AND entry_time >= ? AND entry_time < ?
            GROUP BY account_name, time_slot, day_of_week
            HAVING n >= ? AND avg_pnl > ? AND wr >= ?
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY time_slot, day_of_week ORDER BY (avg_pnl * (wr/100.0)) DESC) as rn
            FROM perf
        )
        SELECT time_slot, day_of_week, account_name FROM ranked WHERE rn = 1
    """, (symbol, start_date, end_date, min_trades, min_pnl, min_wr))
    return {(r["time_slot"], r["day_of_week"]): r["account_name"] for r in cursor.fetchall()}

def run_comparison(symbol):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE symbol=?", (symbol,))
    row = cursor.fetchone()
    if not row or not row[0]:
        print(f"Skipping {symbol}: No data.")
        return
        
    first, last = row
    first_dt = datetime.fromisoformat(first[:10])
    last_dt = datetime.fromisoformat(last[:10])
    
    # WF Params
    W = 120 # Shifting to 120 days for more stability
    H = 30 # Test
    step = 30
    
    results = {"classic": [], "ensemble": [], "statistical": [], "consensus": []}
    
    curr = first_dt
    while curr + timedelta(days=W+H) <= last_dt:
        train_start = curr.strftime("%Y-%m-%d")
        train_end = (curr + timedelta(days=W)).strftime("%Y-%m-%d")
        test_start = train_end
        test_end = (curr + timedelta(days=W+H)).strftime("%Y-%m-%d")
        
        # Build matrices
        m_classic = build_matrix_classic(cursor, symbol, train_start, train_end)
        m_ensemble = build_matrix_ensemble(cursor, symbol, train_start, train_end)
        m_stats = build_matrix_statistical(cursor, symbol, train_start, train_end)
        
        # Consensus = where ALL THREE agree (the most robust)
        m_consensus = {k: v for k, v in m_ensemble.items() if m_classic.get(k) == v and m_stats.get(k) == v}
        
        # Apply OOS
        p_classic = apply_oos(cursor, m_classic, symbol, test_start, test_end)
        p_ensemble = apply_oos(cursor, m_ensemble, symbol, test_start, test_end)
        p_stats = apply_oos(cursor, m_stats, symbol, test_start, test_end)
        p_consensus = apply_oos(cursor, m_consensus, symbol, test_start, test_end)
        
        results["classic"].extend(p_classic)
        results["ensemble"].extend(p_ensemble)
        results["statistical"].extend(p_stats)
        results["consensus"].extend(p_consensus)
        
        curr += timedelta(days=step)
    
    print(f"\n===== STRATEGY COMPARISON REPORT: {symbol} (Train: {W}d, Test: {H}d) =====")
    for model, pnls in results.items():
        if not pnls: continue
        total = sum(pnls)
        sharpe = calculate_sharpe(pnls)
        win_rate = (len([p for p in pnls if p > 0]) / len(pnls) * 100) if pnls else 0
        print(f"[{model.upper()}]")
        print(f"  Total OOS PnL: ${total:,.2f}")
        print(f"  OOS Sharpe:     {sharpe:.2f}")
        print(f"  OOS Win Rate:   {win_rate:.1f}%")
        print(f"  Total Trades:   {len(pnls)}")
        print("-" * 30)
    
    conn.close()

if __name__ == "__main__":
    for s in ["ES"]:
        print(f"Analyzing {s}...")
        run_comparison(s)
