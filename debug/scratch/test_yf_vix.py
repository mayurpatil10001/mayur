
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd

start_date = datetime(2024, 3, 3)
end_date = datetime(2026, 2, 18)

try:
    vix_ticker = yf.Ticker('^VIX')
    data = vix_ticker.history(
        start=start_date.strftime('%Y-%m-%d'),
        end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
        interval='1d',
        auto_adjust=True,
        prepost=False
    )
    print(f"Data length: {len(data)}")
    if not data.empty:
        print(f"First 5 rows:\n{data.head()}")
        print(f"Last 5 rows:\n{data.tail()}")
    else:
        print("Data is empty!")
except Exception as e:
    print(f"Error: {e}")
