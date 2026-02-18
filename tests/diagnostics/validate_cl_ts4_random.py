import sqlite3
import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta

def get_offset(dt):
    year = dt.year
    if year == 2024:
        dst_start = datetime(2024, 3, 10, 2)
        dst_end = datetime(2024, 11, 3, 2)
    elif year == 2025:
        dst_start = datetime(2025, 3, 9, 2)
        dst_end = datetime(2025, 11, 2, 2)
    elif year == 2026:
        dst_start = datetime(2026, 3, 8, 2)
    else: return 5
    if dst_start <= dt < dst_end: return 4
    else: return 5

def validate():
    txt_path = 'CL_TS_4.txt'
    db_path = 'trading_platform.db'
    output_path = r'tests\random_check_CL_TS4.txt'
    
    df_sc = pd.read_csv(txt_path, sep='\t')
    df_sc = df_sc[df_sc['Account'].astype(str).str.contains('TS_4', na=False)]
    
    conn = sqlite3.connect(db_path)
    df_db = pd.read_sql_query("SELECT entry_time, entry_price, side FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL'", conn)
    conn.close()
    
    df_db['utc_time_prefix'] = df_db['entry_time'].str.slice(0, 19).str.replace('T', ' ')
    db_lookup = {}
    for _, row in df_db.iterrows():
        t = row['utc_time_prefix']
        if t not in db_lookup: db_lookup[t] = []
        db_lookup[t].append(row)

    results = []
    sc_count = len(df_sc)
    random_indices = random.sample(range(sc_count), min(10, sc_count))
    
    with open(output_path, 'w') as f:
        f.write("=== Trade Import Validation (Entry Match Only) ===\n\n")
        matches = 0
        for i, idx in enumerate(random_indices):
            sc_row = df_sc.iloc[idx]
            base_time = str(sc_row['Entry DateTime']).split('.')[0].strip().replace('  ', ' ')
            dt = datetime.strptime(base_time, '%Y-%m-%d %H:%M:%S')
            dt_utc = dt + timedelta(hours=get_offset(dt))
            t_utc = dt_utc.strftime('%Y-%m-%d %H:%M:%S')
            
            f.write(f"Trade #{i+1}: SC Entry {sc_row['Entry DateTime']} (Predicted UTC: {t_utc}), Price {sc_row['Entry Price']}\n")
            
            found = False
            # Check a small window (+/- 2 seconds)
            for sec_off in [-2, -1, 0, 1, 2]:
                check_t = (dt_utc + timedelta(seconds=sec_off)).strftime('%Y-%m-%d %H:%M:%S')
                if check_t in db_lookup:
                    for db_row in db_lookup[check_t]:
                        if abs(db_row['entry_price'] - sc_row['Entry Price']) < 0.05:
                            f.write(f"  MATCH FOUND: DB {db_row['entry_time']}, Price {db_row['entry_price']}, Side {db_row['side']}\n")
                            found = True
                            matches += 1
                            break
                if found: break
            
            if not found:
                f.write("  RESULT: NOT FOUND IN DB\n")
            f.write("\n")
            
        f.write(f"Summary: {matches}/{min(10, sc_count)} random trades matched by Entry Time & Price.\n")
        
    print(f"Validation complete. Results saved to {output_path}")

if __name__ == "__main__":
    validate()
