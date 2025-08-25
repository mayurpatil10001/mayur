"""
Test Stooq.com integration for free market data
"""

from trading_platform.services.free_market_data import FreeMarketDataService
from datetime import datetime, timedelta

def test_stooq_integration():
    print('Testing Stooq.com free market data service...')

    service = FreeMarketDataService()

    # Test connectivity first
    print('Testing connectivity to Stooq.com...')
    if service.test_connectivity():
        print('✅ Stooq.com is accessible')
    else:
        print('❌ Stooq.com connectivity failed')
        return False

    # Test fetching recent SPY data
    print('\nFetching recent SPY data...')
    try:
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=10)     # 10 days ago
        
        spy_data = service.fetch_spy_data(start_date, end_date)
        
        print(f'✅ SPY Data Success:')
        print(f'   Records: {spy_data.total_records}')
        print(f'   Quality: {spy_data.data_quality_score:.2%}')
        print(f'   Date range: {spy_data.data.index[0].date()} to {spy_data.data.index[-1].date()}')
        
        close_prices = spy_data.data['Close']
        print(f'   Price range: ${close_prices.min():.2f} - ${close_prices.max():.2f}')
        print(f'   Latest close: ${close_prices.iloc[-1]:.2f}')
        
    except Exception as e:
        print(f'❌ SPY fetch failed: {e}')
        return False

    # Test fetching QQQ data
    print('\nFetching recent QQQ data...')
    try:
        qqq_data = service.fetch_qqq_data(start_date, end_date)
        
        print(f'✅ QQQ Data Success:')
        print(f'   Records: {qqq_data.total_records}')
        print(f'   Quality: {qqq_data.data_quality_score:.2%}')
        
        close_prices = qqq_data.data['Close']
        print(f'   Price range: ${close_prices.min():.2f} - ${close_prices.max():.2f}')
        print(f'   Latest close: ${close_prices.iloc[-1]:.2f}')
        
    except Exception as e:
        print(f'❌ QQQ fetch failed: {e}')
        return False

    # Test fetching VIX data
    print('\nFetching recent VIX data...')
    try:
        vix_data = service.fetch_vix_data(start_date, end_date)
        
        print(f'✅ VIX Data Success:')
        print(f'   Records: {vix_data.total_records}')
        print(f'   Quality: {vix_data.data_quality_score:.2%}')
        
        close_prices = vix_data.data['Close']
        print(f'   VIX range: {close_prices.min():.2f} - {close_prices.max():.2f}')
        print(f'   Latest VIX: {close_prices.iloc[-1]:.2f}')
        
    except Exception as e:
        print(f'❌ VIX fetch failed: {e}')
        return False

    print('\n✅ Stooq.com integration test complete!')
    return True

if __name__ == "__main__":
    success = test_stooq_integration()
    if success:
        print("\n🎉 All tests passed! Stooq.com integration is working.")
    else:
        print("\n❌ Some tests failed. Check the errors above.")