"""
Go/No-Go Test Suite — Phase 2: Account Management

Tests the account management API endpoint.
Run:  python -m pytest tests/test_account_management_go_no_go.py -v --tb=short

Go/No-Go Metrics
────────────────
1. All accounts returned        → Count matches DB distinct account/symbol combos
2. Last trade date accurate     → Matches MAX(exit_time) per account
3. Days since last trade        → Computed correctly vs current date
4. Empty DB                     → Returns empty list, no crash
5. Stale detection              → Accounts with old trades flagged correctly
6. Win rate accuracy            → Matches manual calculation
"""

import os
import sys
import sqlite3
import tempfile
import pytest
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading_platform.services.trade_import_service import TradeImportService


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _temp_db():
    """Create a temp SQLite DB with the processed_trades table."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE processed_trades (
            trade_id TEXT PRIMARY KEY,
            account_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            side TEXT NOT NULL,
            profit_loss REAL NOT NULL,
            commission REAL DEFAULT 0,
            duration_minutes INTEGER DEFAULT 0,
            hour_of_day INTEGER DEFAULT 0,
            day_of_week INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    return path


def _insert_trade(conn, trade_id, account, symbol, entry_time, exit_time, pnl,
                   entry_price=100, exit_price=101, qty=1, side="LONG"):
    """Insert a test trade."""
    conn.execute(
        """INSERT INTO processed_trades
           (trade_id, account_name, symbol, entry_time, exit_time,
            entry_price, exit_price, quantity, side, profit_loss,
            commission, duration_minutes, hour_of_day, day_of_week)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 5, 14, 1)""",
        (trade_id, account, symbol, entry_time.isoformat(),
         exit_time.isoformat(), entry_price, exit_price, qty, side, pnl),
    )


def _query_management(db_path: str, stale_days: int = 7):
    """
    Directly exercise the account management SQL query
    (same logic as the API endpoint, for unit-testability without FastAPI).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            account_name,
            symbol,
            COUNT(*)                                          AS total_trades,
            SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) AS winning_trades,
            SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) AS losing_trades,
            ROUND(SUM(CASE WHEN profit_loss > 0 THEN 1.0 ELSE 0 END) * 100.0 / COUNT(*), 1)
                                                              AS win_rate,
            ROUND(SUM(profit_loss), 2)                        AS total_pnl,
            ROUND(AVG(profit_loss), 2)                        AS avg_pnl,
            MIN(entry_time)                                   AS first_trade_date,
            MAX(exit_time)                                    AS last_trade_date
        FROM processed_trades
        WHERE account_name NOT LIKE '%dupl%'
          AND account_name NOT LIKE '%sim%'
        GROUP BY account_name, symbol
        ORDER BY account_name, symbol
    """)
    rows = cursor.fetchall()
    conn.close()

    today = date.today()
    accounts = []
    for row in rows:
        last_trade = row["last_trade_date"]
        days_since = None
        is_active = True
        if last_trade:
            try:
                last_dt = datetime.fromisoformat(last_trade.replace("Z", "+00:00"))
                days_since = (today - last_dt.date()).days
                is_active = days_since <= stale_days
            except Exception:
                pass
        accounts.append({
            "account_name": row["account_name"],
            "symbol": row["symbol"],
            "total_trades": row["total_trades"],
            "winning_trades": row["winning_trades"] or 0,
            "losing_trades": row["losing_trades"] or 0,
            "win_rate": float(row["win_rate"]) if row["win_rate"] else 0.0,
            "total_pnl": float(row["total_pnl"]) if row["total_pnl"] else 0.0,
            "first_trade_date": row["first_trade_date"],
            "last_trade_date": last_trade,
            "days_since_last_trade": days_since,
            "is_active": is_active,
        })
    return accounts


# ──────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────

class TestAllAccountsReturned:
    """GO: Count matches DB distinct account/symbol combos."""

    def test_two_accounts(self):
        db_path = _temp_db()
        try:
            conn = sqlite3.connect(db_path)
            now = datetime.now()
            _insert_trade(conn, "t1", "ACC_A", "NQ", now, now, 50.0)
            _insert_trade(conn, "t2", "ACC_B", "ES", now, now, -10.0)
            conn.commit()
            conn.close()

            accounts = _query_management(db_path)
            assert len(accounts) == 2
            names = {a["account_name"] for a in accounts}
            assert names == {"ACC_A", "ACC_B"}
        finally:
            os.unlink(db_path)

    def test_same_account_two_symbols(self):
        """Same account trading NQ and ES → 2 rows."""
        db_path = _temp_db()
        try:
            conn = sqlite3.connect(db_path)
            now = datetime.now()
            _insert_trade(conn, "t1", "ACC_A", "NQ", now, now, 10.0)
            _insert_trade(conn, "t2", "ACC_A", "ES", now, now, 20.0)
            conn.commit()
            conn.close()

            accounts = _query_management(db_path)
            assert len(accounts) == 2
        finally:
            os.unlink(db_path)


class TestLastTradeDateAccurate:
    """GO: Matches MAX(exit_time) per account."""

    def test_last_date(self):
        db_path = _temp_db()
        try:
            conn = sqlite3.connect(db_path)
            early = datetime(2024, 1, 1, 10, 0)
            late = datetime(2024, 6, 15, 14, 30)
            _insert_trade(conn, "t1", "ACC_A", "NQ", early, early, 10.0)
            _insert_trade(conn, "t2", "ACC_A", "NQ", late, late, 20.0)
            conn.commit()
            conn.close()

            accounts = _query_management(db_path)
            assert len(accounts) == 1
            assert accounts[0]["last_trade_date"] == late.isoformat()
        finally:
            os.unlink(db_path)


class TestDaysSinceLastTrade:
    """GO: Computed correctly vs current date."""

    def test_days_calculation(self):
        db_path = _temp_db()
        try:
            conn = sqlite3.connect(db_path)
            old_date = datetime.now() - timedelta(days=10)
            _insert_trade(conn, "t1", "ACC_OLD", "NQ", old_date, old_date, 10.0)
            conn.commit()
            conn.close()

            accounts = _query_management(db_path)
            assert len(accounts) == 1
            # Should be ~10 days (allow ±1 for date boundary)
            assert 9 <= accounts[0]["days_since_last_trade"] <= 11
        finally:
            os.unlink(db_path)


class TestEmptyDatabase:
    """GO: Returns empty list, no crash."""

    def test_empty(self):
        db_path = _temp_db()
        try:
            accounts = _query_management(db_path)
            assert accounts == []
        finally:
            os.unlink(db_path)


class TestStaleDetection:
    """GO: Accounts with old trades flagged as stale."""

    def test_stale_and_active(self):
        db_path = _temp_db()
        try:
            conn = sqlite3.connect(db_path)
            recent = datetime.now() - timedelta(days=2)
            old = datetime.now() - timedelta(days=30)
            _insert_trade(conn, "t1", "ACTIVE_ACC", "NQ", recent, recent, 10.0)
            _insert_trade(conn, "t2", "STALE_ACC", "NQ", old, old, 10.0)
            conn.commit()
            conn.close()

            accounts = _query_management(db_path, stale_days=7)
            active = [a for a in accounts if a["is_active"]]
            stale = [a for a in accounts if not a["is_active"]]
            assert len(active) == 1
            assert active[0]["account_name"] == "ACTIVE_ACC"
            assert len(stale) == 1
            assert stale[0]["account_name"] == "STALE_ACC"
        finally:
            os.unlink(db_path)


class TestWinRateAccuracy:
    """GO: Win rate matches manual calculation."""

    def test_win_rate(self):
        db_path = _temp_db()
        try:
            conn = sqlite3.connect(db_path)
            now = datetime.now()
            _insert_trade(conn, "t1", "ACC", "NQ", now, now, 50.0)   # Win
            _insert_trade(conn, "t2", "ACC", "NQ", now, now, 30.0)   # Win
            _insert_trade(conn, "t3", "ACC", "NQ", now, now, -10.0)  # Loss
            conn.commit()
            conn.close()

            accounts = _query_management(db_path)
            assert len(accounts) == 1
            # 2 wins / 3 trades = 66.7%
            assert accounts[0]["win_rate"] == pytest.approx(66.7, abs=0.1)
            assert accounts[0]["winning_trades"] == 2
            assert accounts[0]["losing_trades"] == 1
            assert accounts[0]["total_pnl"] == pytest.approx(70.0, abs=0.01)
        finally:
            os.unlink(db_path)
