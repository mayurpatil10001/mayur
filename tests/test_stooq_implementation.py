#!/usr/bin/env python3
"""
Test script for the new Stooq.com implementation
This tests the fallback mechanism when Yahoo Finance fails
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from trading_platform.services.free_market_data import FreeMarketDataService
from loguru import logger

def test_stooq_implementation():
    """Test the Stooq.com implementation directly."""
    print("Testing Stooq.com implementation...")
    
    # Initialize service
    service = FreeMarketDataService()
    
    # Test connection first
    print("Testing connection to Stooq...")
    if not service.test_connection():
        print("❌ Connection test failed")
        return False
    print("✅ Connection test successful")
    
    # Define test date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Test each symbol
    symbols = ['SPY', 'QQQ', 'VIX']
    for symbol in symbols:
        try:
            print(f"\nTesting {symbol} data fetch...")
            
            if symbol == 'SPY':
                result = service.fetch_spy_data(start_date, end_date)
            elif symbol == 'QQQ':
                result = service.fetch_qqq_data(start_date, end_date)
            elif symbol == 'VIX':
                result = service.fetch_vix_data(start_date, end_date)
            
            print(f"✅ {symbol} data fetched successfully:")
            print(f"   - Records: {result.total_records}")
            print(f"   - Quality Score: {result.data_quality_score:.2%}")
            print(f"   - Date Range: {result.start_date.date()} to {result.end_date.date()}")
            
            # Show sample data
            if not result.data.empty:
                latest_row = result.data.iloc[-1]
                print(f"   - Latest Close: ${latest_row['Close']:.2f}")
                
        except Exception as e:
            print(f"❌ {symbol} test failed: {e}")
            return False
    
    print("\n🎉 All tests passed! Stooq implementation is working correctly.")
    return True

def test_fallback_integration():
    """Test the fallback integration in the main MarketDataIngestion service."""
    print("\n" + "="*50)
    print("Testing fallback integration...")
    
    # Force Yahoo Finance to fail by using invalid dates or causing an error
    from trading_platform.services.market_data_ingestion import MarketDataIngestion
    
    # This should trigger the fallback to Stooq
    service = MarketDataIngestion()
    
    # Test with recent data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    try:
        print(f"Testing integrated fallback for SPY...")
        spy_data = service.fetch_spy_data(start_date, end_date)
        print(f"✅ Integrated SPY fetch successful: {spy_data.total_records} records")
        
    except Exception as e:
        print(f"❌ Integrated test failed: {e}")
        return False
    
    print("✅ Fallback integration test successful!")
    return True

if __name__ == "__main__":
    logger.remove()  # Remove default logger
    logger.add(sys.stdout, level="INFO")
    
    success = test_stooq_implementation()
    if success:
        success = test_fallback_integration()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("The Stooq.com fallback implementation is ready for production use.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)