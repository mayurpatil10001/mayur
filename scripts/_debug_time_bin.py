import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import datetime
from trading_platform.services.time_bin_analyzer import TimeBin
from trading_platform.database.database import get_db_context
from trading_platform.models.database import ProcessedTrade as PT

with get_db_context() as session:
    rows = session.query(
        PT.trade_id, PT.account_name, PT.entry_time, PT.hour_of_day
    ).filter(PT.account_name == 'V500_SIM15', PT.hour_of_day == 9).limit(10).all()

    print(f'Raw rows count: {len(rows)}')
    tb30 = TimeBin('V500_SIM15', 9, 30)
    tb00 = TimeBin('V500_SIM15', 9, 0)
    for r in rows:
        et = r.entry_time
        et_type = type(et).__name__
        if isinstance(et, str):
            et = datetime.datetime.fromisoformat(et)
        m30 = tb30.matches_trade_time(et)
        m00 = tb00.matches_trade_time(et)
        print(f"  tid={r.trade_id}, entry={et}, type={et_type}, h={r.hour_of_day}, m09:00={m00}, m09:30={m30}")
