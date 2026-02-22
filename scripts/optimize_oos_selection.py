import sqlite3
import math
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "trading_platform.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_parameter_search(symbol="NQ"):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE symbol=?", (symbol,))
    row = cursor.fetchone()
    if not row or not row[0]: return
    first_dt, last_dt = datetime.fromisoformat(row[0][:10]), datetime.fromisoformat(row[1][:10])
    
    # Grid search parameters
    windows = [60, 90, 120, 180, 270, 360]
    min_trades_list = [5, 15]
    conf_thresholds = [0.0, 0.9]
    
    best_config = None
    best_sharpe = -99
    
    for W in windows:
        for MT in min_trades_list:
            # Pre-calculate matrices for all folds to save time
            folds = []
            curr = first_dt
            while curr + timedelta(days=W+21) <= last_dt:
                train_start = curr.strftime("%Y-%m-%d")
                train_end = (curr + timedelta(days=W)).strftime("%Y-%m-%d")
                test_start = train_end
                test_end = (curr + timedelta(days=W+21)).strftime("%Y-%m-%d")
                
                # Fetch all candidates for Ensemble logic (simulating _get_ensemble_recommendations)
                # We'll just fetch the best ones per window
                sub_windows = [W, W//2, W//3]
                fold_data = {} # (time, day) -> [(acct, score)...]
                
                for sw in sub_windows:
                    if sw < 10: continue
                    sw_start = (datetime.fromisoformat(train_end) - timedelta(days=sw)).strftime("%Y-%m-%d")
                    cursor.execute("""
                        SELECT account_name,
                            printf('%02d:%02d',
                                CAST(strftime('%H', entry_time) AS INTEGER),
                                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                            ) as time_slot,
                            CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                            AVG(profit_loss) as avg_pnl, COUNT(*) as n,
                            AVG(profit_loss*profit_loss) - (AVG(profit_loss)*AVG(profit_loss)) as var
                        FROM processed_trades WHERE symbol=? AND entry_time>=? AND entry_time<?
                        GROUP BY account_name, time_slot, day_of_week HAVING n >= ?
                    """, (symbol, sw_start, train_end, max(2, MT * sw // W)))
                    
                    for r in cursor.fetchall():
                        key = (r["time_slot"], r["day_of_week"])
                        sd = math.sqrt(max(1.0, r["var"]))
                        sh = r["avg_pnl"] / (sd / 10.0) if sd > 0 else 0
                        score = (min(2.0, r["avg_pnl"] / 25.0) * 0.6) + (min(2.0, sh / 4.0) * 0.4)
                        if key not in fold_data: fold_data[key] = defaultdict(float)
                        fold_data[key][r["account_name"]] += score * (1.0 if sw==W else 0.7)
                
                # Apply OOS for this fold across all thresholds
                cursor.execute("""
                    SELECT account_name, profit_loss, entry_time,
                        printf('%02d:%02d',
                            CAST(strftime('%H', entry_time) AS INTEGER),
                            CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                        ) as time_slot,
                        CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
                    FROM processed_trades WHERE symbol=? AND entry_time>=? AND entry_time<?
                """, (symbol, test_start, test_end))
                oos_trades = [dict(r) for r in cursor.fetchall()]
                
                folds.append({"train_matrix": fold_data, "oos_trades": oos_trades})
                curr += timedelta(days=21)

            # Analyze thresholds
            for CT in conf_thresholds:
                total_pnls = []
                for f in folds:
                    for t in f["oos_trades"]:
                        key = (t["time_slot"], t["day_of_week"])
                        candidates = f["train_matrix"].get(key)
                        if candidates:
                            best_acct = max(candidates, key=candidates.get)
                            conf = candidates[best_acct]
                            if conf >= CT and best_acct == t["account_name"]:
                                total_pnls.append(t["profit_loss"])
                
                if not total_pnls: continue
                
                pnl = sum(total_pnls)
                mean = pnl / len(total_pnls)
                var = sum((x - mean)**2 for x in total_pnls) / max(1, len(total_pnls)-1)
                std = math.sqrt(var)
                sharpe = (mean / std * math.sqrt(1000)) if std > 0 else 0
                
                if pnl > 0:
                    print(f"!!! PROFITABLE FOUND !!! [{symbol}] W:{W} MT:{MT} CT:{CT:.2f} -> PnL: ${pnl:,.0f}, Sharpe: {sharpe:.2f}, Trades: {len(total_pnls)}")
                else:
                    print(f"[{symbol}] W:{W} MT:{MT} CT:{CT:.2f} -> PnL: ${pnl:,.0f}, Sharpe: {sharpe:.2f}, Trades: {len(total_pnls)}")
                
                if sharpe > best_sharpe and len(total_pnls) > 100:
                    best_sharpe = sharpe
                    best_config = (W, MT, CT, pnl, sharpe)

    print(f"\nBEST FOR {symbol}: W={best_config[0]} MT={best_config[1]} CT={best_config[2]:.2f} -> Sharpe {best_config[4]:.2f}")
    conn.close()

if __name__ == "__main__":
    for s in ["ES", "CL", "GC"]:
        try: run_parameter_search(s)
        except Exception as e: print(f"Error {s}: {e}")
