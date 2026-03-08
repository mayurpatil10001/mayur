import requests

r = requests.get('http://localhost:8000/api/v1/accounts/?size=1000')
data = r.json()
# The structure is APIResponse -> data (PaginatedResponse) -> items
items = data.get('data', {}).get('items', [])
vsim16 = [i['name'] for i in items if 'V_SIM16' in i['name']]

print(f"Total accounts in API response: {len(items)}")
print(f"V_SIM16 matches: {vsim16}")
