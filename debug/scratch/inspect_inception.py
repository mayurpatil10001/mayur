import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Inception of V_SIM16 account:")
c.execute("""
    SELECT side, entry_time, exit_time, quantity, entry_price, exit_price 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
    ORDER BY entry_time ASC 
    LIMIT 30
""")
net = 0
for r in c.fetchall():
    side = r[0]
    qty = r[3]
    if side == 'SHORT': # SELL entry -> BUY exit
         # entry is SELL (-), exit is BUY (+)
         net -= qty # at entry
         net += qty # at exit -> it's a trade, so it should be balanced!
    else: # LONG
         net += qty
         net -= qty
    
    # Wait, 'processed_trades' stores COMPLETED trades.
    # Every row in 'processed_trades' means one pairing was completed.
    # So the net position contributed by 'processed_trades' is ALWAYS 0.
    # The only way to have a net position is the 'pending_fills' table!
    
    print(f"  {r[1]} {side:6s} qty={qty} px={r[4]}/{r[5]}")

# Let's check the very first PENDING fills for V_SIM16
print("\nFirst 30 PENDING FILLS for V_SIM16 (The source of current imbalance):")
c.execute("""
    SELECT side, entry_time, quantity, price 
    FROM pending_fills 
    WHERE account_name = 'V_SIM16' 
    ORDER BY entry_time ASC 
    LIMIT 30
""")
for r in c.fetchall():
    print(f"  {r[1]} {r[0]:6s} qty={r[2]} px={r[3]}")

conn.close()
