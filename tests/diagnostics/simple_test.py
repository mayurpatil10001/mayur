import sys
import os

try:
    print("Testing Stooq implementation...")
    
    # Add path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from trading_platform.services.free_market_data import FreeMarketDataService
    print("✅ Import successful")
    
    service = FreeMarketDataService()
    print("✅ Service initialized")
    
    # Test connection
    result = service.test_connection()
    print(f"Connection test: {'✅ Success' if result else '❌ Failed'}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()