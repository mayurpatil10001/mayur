import time
import urllib.request
import json

base_url = "http://127.0.0.1:8000/api/v1/analytics/recommendations"

def test_endpoint(name, path):
    print(f"Testing {name}...")
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(f"{base_url}/{path}")
        duration = time.time() - t0
        print(f"  First call: {duration:.2f}s")
        
        t1 = time.time()
        resp2 = urllib.request.urlopen(f"{base_url}/{path}")
        duration2 = time.time() - t1
        print(f"  Second call (should be cached): {duration2:.2f}s")
        
        return duration, duration2
    except Exception as e:
        print(f"  Error: {e}")
        return None, None

print("Verification of Caching & Optimization")
print("-" * 40)

matrix_path = "matrix/NQ?selection_logic=classic"
stats_path = "combined-stats/NQ?selection_logic=classic"
backtest_path = "backtest/NQ?selection_logic=classic"

test_endpoint("Matrix", matrix_path)
test_endpoint("Combined Stats", stats_path)
test_endpoint("Backtest", backtest_path)
