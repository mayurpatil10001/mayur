
import os
import sys
from datetime import datetime
# Add the project root to sys.path
sys.path.append(os.getcwd())

from trading_platform.database.database import SessionLocal
from trading_platform.services.vix_regime_analyzer import VIXDataIntegration

db = SessionLocal()
service = VIXDataIntegration(db_session=db)

start_date = datetime(2024, 3, 3)
end_date = datetime(2026, 2, 18)
account_name = "NQ"

try:
    print(f"Fetching equity curve for {account_name} from {start_date} to {end_date}")
    result = service.get_equity_curve_with_regimes(account_name, start_date, end_date)
    print(f"Result length: {len(result.get('equity_curve', []))}")
    if len(result.get('equity_curve', [])) == 0:
        # Debug why it's empty
        from trading_platform.models.database import ProcessedTrade
        from sqlalchemy import or_
        trades = db.query(ProcessedTrade).filter(
            or_(
                ProcessedTrade.account_name == account_name,
                ProcessedTrade.symbol.startswith(account_name)
            )
        ).filter(ProcessedTrade.entry_time >= start_date).filter(ProcessedTrade.entry_time <= end_date).all()
        print(f"Internal trade count: {len(trades)}")
        if trades:
            print(f"First trade: {trades[0].symbol}, {trades[0].entry_time}")
            # Check VIX data for that date
            from trading_platform.models.time_bin_analytics import MarketData
            vix = db.query(MarketData).filter(MarketData.symbol == 'VIX', MarketData.date == trades[0].entry_time.date()).first()
            print(f"VIX for {trades[0].entry_time.date()}: {vix}")
        
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
finally:
    db.close()
