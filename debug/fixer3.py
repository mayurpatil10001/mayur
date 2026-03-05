import os

fp = r'c:\SierraChart\SC results WF\trading_platform\services\trade_import_service.py'
with open(fp, 'r', encoding='utf-8') as f:
    text = f.read()

target = """        conn = sqlite3.connect(self.db_path)
        touched = set()
        try:
            for pt in parsed_objs:"""

replacement = """        conn = sqlite3.connect(self.db_path)
        touched = set()
        try:
            # AUTO-CLEANUP: If importing high-integrity Fills, overwrite any existing trades in this specific window.
            if parsed_objs:
                min_t = min(pt.entry_datetime for pt in parsed_objs).isoformat()
                max_t = max(pt.exit_datetime for pt in parsed_objs).isoformat()
                unique_accs = list(set(pt.account_name for pt in parsed_objs))
                
                cursor = conn.cursor()
                total_wiped = 0
                for acc_name in unique_accs:
                    cursor.execute(
                        "DELETE FROM processed_trades WHERE account_name = ? AND entry_time >= ? AND exit_time <= ?",
                        (acc_name, min_t, max_t)
                    )
                    total_wiped += cursor.rowcount
                
                if total_wiped > 0:
                    import logging
                    logging.getLogger(__name__).info(f"Auto-cleaned {total_wiped} overlapping trades to prevent double-counting.")
                    result.stats['auto_cleaned_count'] = total_wiped

            for pt in parsed_objs:"""

if target in text:
    text = text.replace(target, replacement)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS")
else:
    print("FAILED TO MATCH")
