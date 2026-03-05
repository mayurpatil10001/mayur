import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import datetime as dt
from zoneinfo import ZoneInfo
from tests.test_binary_benchmark_1218 import _load_binary_fills_for_ny_1218

fills = _load_binary_fills_for_ny_1218()
ny = ZoneInfo("America/New_York")

print("Fills loaded:", len(fills))
for f in fills[:20]:
    print(f['timestamp'], f['side'], f['qty'], f['price'], f.get('internal_order_id', ''))
