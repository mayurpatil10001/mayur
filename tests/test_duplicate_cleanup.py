#!/usr/bin/env python3
"""
Test script to verify duplicate cleanup functionality
"""

import sqlite3
import sys
from pathlib import Path

def test_duplicate_cleanup():
    """Test the duplicate cleanup logic"""
    
    # Connect to database
    db_path = Path("trading_platform.db")
    if not db_path.exists():
        print("❌ Database file not found!")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("🔍 Checking for duplicate trades...")
    
    # Find duplicates using the same logic as the API
    duplicate_query = """
    SELECT 
        COUNT(*) as duplicate_count,
        GROUP_CONCAT(id) as duplicate_ids,
        entry_time, exit_time, account_name, symbol, quantity, entry_price, exit_price, profit_loss
    FROM processed_trades 
    GROUP BY entry_time, exit_time, account_name, symbol, quantity, entry_price, exit_price, profit_loss
    HAVING COUNT(*) > 1
    """
    
    cursor.execute(duplicate_query)
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ No duplicate trades found!")
        conn.close()
        return True
    
    print(f"📊 Found {len(duplicates)} groups of duplicate trades:")
    
    total_duplicates_to_remove = 0
    for i, row in enumerate(duplicates):
        duplicate_count = row[0]
        duplicate_ids = row[1].split(',')
        entry_time = row[2]
        account_name = row[4]
        symbol = row[5]
        
        duplicates_to_remove = duplicate_count - 1  # Keep one, remove the rest
        total_duplicates_to_remove += duplicates_to_remove
        
        print(f"  {i+1}. {account_name} {symbol} at {entry_time}")
        print(f"     - {duplicate_count} copies found (IDs: {duplicate_ids})")
        print(f"     - Will remove {duplicates_to_remove} duplicates")
        print()
    
    print(f"📈 Summary:")
    print(f"   - Duplicate groups: {len(duplicates)}")
    print(f"   - Total duplicates to remove: {total_duplicates_to_remove}")
    
    # Ask if user wants to proceed with cleanup
    response = input("\n❓ Do you want to proceed with cleanup? (y/N): ").strip().lower()
    
    if response == 'y':
        print("\n🧹 Starting cleanup...")
        
        removed_count = 0
        for row in duplicates:
            duplicate_ids = row[1].split(',')
            ids_to_remove = duplicate_ids[1:]  # Keep first, remove rest
            
            for trade_id in ids_to_remove:
                cursor.execute("DELETE FROM processed_trades WHERE id = ?", (int(trade_id),))
                if cursor.rowcount > 0:
                    removed_count += 1
        
        conn.commit()
        print(f"✅ Successfully removed {removed_count} duplicate trades!")
        
        # Verify cleanup
        cursor.execute(duplicate_query)
        remaining_duplicates = cursor.fetchall()
        
        if not remaining_duplicates:
            print("🎉 All duplicates have been cleaned!")
        else:
            print(f"⚠️ {len(remaining_duplicates)} duplicate groups still remain")
    
    else:
        print("❌ Cleanup cancelled")
    
    conn.close()
    return True

if __name__ == "__main__":
    test_duplicate_cleanup()