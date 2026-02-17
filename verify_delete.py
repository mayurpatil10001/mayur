
import sqlite3

def verify_cl_deletion():
    try:
        conn = sqlite3.connect('trading_platform.db')
        cursor = conn.cursor()
        
        # Check for CL in symbol column
        cursor.execute("SELECT COUNT(*) FROM processed_trades WHERE symbol = 'CL' OR symbol LIKE 'CL%'")
        count = cursor.fetchone()[0]
        
        # Also check distinct symbols just in case
        cursor.execute("SELECT DISTINCT symbol FROM processed_trades")
        symbols = [row[0] for row in cursor.fetchall()]
        
        print(f"Verification Results:")
        print(f"Total CL trades found: {count}")
        print(f"Current unique symbols in DB: {', '.join(symbols) if symbols else 'None'}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    verify_cl_deletion()
