import sqlite3
import pandas as pd
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
    else:
        return 5
    if dst_start <= dt < dst_end:
        return 4
    else:
        return 5

def check_daily_counts():
    db_path = 'trading_platform.db'
    txt_path = 'CL_TS_4.txt'
    
    conn = sqlite3.connect(db_path)
    df_db = pd.read_sql_query("SELECT substr(entry_time, 1, 10) as date, count(*) as db_count FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL' GROUP BY date", conn)
    conn.close()
    
    df_sc_raw = pd.read_csv(txt_path, sep='\t')
    df_sc_raw = df_sc_raw[df_sc_raw['Account'].astype(str).str.contains('TS_4', na=False)]
    
    def to_utc_date(ts_str):
        base = str(ts_str).split('.')[0].strip().replace('  ', ' ')
        try:
            dt = datetime.strptime(base, '%Y-%m-%d %H:%M:%S')
            dt_utc = dt + timedelta(hours=get_offset(dt))
            return dt_utc.strftime('%Y-%m-%d')
        except:
            return None

    df_sc_raw['date'] = df_sc_raw['Entry DateTime'].apply(to_utc_date)
    df_sc = df_sc_raw.groupby('date').size().reset_index(name='sc_count')
    
    merged = pd.merge(df_db, df_sc, on='date', how='outer').fillna(0)
    merged['diff'] = merged['db_count'] - merged['sc_count']
    
    print("Days with mismatches in trade counts (after UTC adjustment):")
    mismatches = merged[merged['diff'] != 0]
    print(mismatches.head(20))
    print(f"\nTotal days: {len(merged)}")
    print(f"Days with exact count match: {len(merged[merged['diff'] == 0])}")
    
    match_perc = (len(merged[merged['diff'] == 0]) / len(merged)) * 100
    print(f"\nOverall Daily Count Match: {match_perc:.2f}%")

if __name__ == "__main__":
    check_daily_counts()
