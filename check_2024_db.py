import requests

r = requests.get('http://localhost:8000/api/system/accounts')
data = r.json()

print("Accounts with trades in 2024 in the DB:")
found = False
for acc in data:
    if acc.get('first_trade_date') and '2024' in acc['first_trade_date']:
        print(f"{acc['name']} ({acc['base_symbol']}): First trade {acc['first_trade_date']}, PnL ${acc['total_pnl']}")
        found = True
if not found:
    print("None found.")
