
from trading_platform.services.market_data_ingestion import MarketDataIngestion
from datetime import datetime, timedelta
import pandas as pd

# Try a smaller range first
end_date = datetime(2026, 2, 18)
start_date = end_date - timedelta(days=30)

service = MarketDataIngestion()
try:
    print(f"Fetching VIX for {start_date} to {end_date}")
    result = service.fetch_vix_data(start_date, end_date)
    print(f"Success! Records: {result.total_records}")
except Exception as e:
    import traceback
    print(f"Failed: {e}")
    traceback.print_exc()
