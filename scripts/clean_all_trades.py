
import sqlite3

def clean_all():
    # Because the import accidentally imported EVERYTHING (13M records), 
    # we need to nuke it all and let the user re-import cleanly.
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    print("Deleting ALL trades to clean up the accidental Global Import...")
    cursor.execute("DELETE FROM processed_trades")
    print(f"Deleted {cursor.rowcount} records.")
    
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    print("Cleanup complete.")

if __name__ == '__main__':
    clean_all()
