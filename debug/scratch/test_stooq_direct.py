
import requests
from datetime import datetime

symbol = 'vi.f'
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 2, 20)

d1 = start_date.strftime('%Y%m%d')
d2 = end_date.strftime('%Y%m%d')

url = f"https://stooq.com/q/d/l/?s={symbol}&d1={d1}&d2={d2}&i=d"
print(f"URL: {url}")

r = requests.get(url)
print(f"Status: {r.status_code}")
print(f"Content Length: {len(r.text)}")
print(f"Content Preview:\n{r.text[:500]}")
