import sys
import os

try:
    print("Testing Stooq implementation...")
    
    # Add path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from trading_platform.services.free_market_data import FreeMarketDataService
    print("[OK] Import successful")

    service = FreeMarketDataService()
    print("[OK] Service initialized")

    # Test connection
    result = service.test_connection()
    print(f"Connection test: {'[OK] Success' if result else '[ERROR] Failed'}")

except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()