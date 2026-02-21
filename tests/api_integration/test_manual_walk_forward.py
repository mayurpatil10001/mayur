import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from trading_platform.api.main import app
import sqlite3
from datetime import datetime, timedelta

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_db_connection():
    with patch('sqlite3.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.row_factory = sqlite3.Row
        yield mock_conn, mock_cursor

def test_walk_forward_logic(client, mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection

    # 1. Date Range Query
    # SELECT MIN(entry_time), MAX(entry_time) ...
    mock_cursor.fetchone.return_value = ['2023-01-01 00:00:00', '2023-06-30 23:59:59']

    # 2. Sequential fetchall returns
    # We need to simulate the loop.
    # The code builds matrix then applies it.
    
    # Mock row data for matrix (build_matrix)
    # Returns: time_slot, day_of_week, account_name
    matrix_rows = [
        {'time_slot': '09:30', 'day_of_week': 1, 'account_name': 'ACC1'},
        {'time_slot': '10:00', 'day_of_week': 1, 'account_name': 'ACC2'},
    ]
    
    # Mock row data for OOS trades (apply_matrix)
    # Returns: account_name, profit_loss, time_slot, day_of_week
    # We want to test max_drawdown logic.
    # Let's create a sequence of PnLs: +100, -200, +50, -300
    # Equity: 0 -> 100 -> -100 (DD 200) -> -50 (DD 150) -> -350 (DD 450)
    # Peak starts at 0.
    # 1. P=+100, Eq=100. Peak=100. DD=0.
    # 2. P=-200, Eq=-100. Peak=100. DD=200. MaxDD=200.
    # 3. P=+50, Eq=-50. Peak=100. DD=150. MaxDD=200.
    # 4. P=-300, Eq=-350. Peak=100. DD=450. MaxDD=450.
    # So max_drawdown_dollars should be 450.
    
    oos_rows = [
        {'account_name': 'ACC1', 'profit_loss': 100.0, 'time_slot': '09:30', 'day_of_week': 1},
        {'account_name': 'ACC1', 'profit_loss': -200.0, 'time_slot': '09:30', 'day_of_week': 1}, # Matches ACC1
        {'account_name': 'ACC2', 'profit_loss': 50.0, 'time_slot': '10:00', 'day_of_week': 1},
        {'account_name': 'ACC2', 'profit_loss': -300.0, 'time_slot': '10:00', 'day_of_week': 1}, # Matches ACC2
    ]
    
    # Configure side_effect for fetchall
    # First call is in build_matrix (for loop iteration 1)
    # Second call is in apply_matrix (for loop iteration 1)
    # Then loop might continue.
    # We will simulate just 1 fold by limiting the date range or just providing enough data for one loop.
    
    # Just return these repeatedly
    mock_cursor.fetchall.side_effect = [
        matrix_rows, # matrix
        oos_rows,    # trades
        [],          # next matrix (empty breaks loop or returns empty) - wait, if matrix empty, loop continues?
                     # Actually loop breaks if test_end > last_date.
    ]

    # Force the date arithmetic to produce exactly 1 fold if possible, 
    # but the loop runs until test_end > last_date.
    # We returned date range 2023-01-01 to 2023-06-30.
    # Default params: training_days=90, testing_days=21.
    # Fold 1: Train Jan 1 - Mar 31 (90d). Test Apr 1 - Apr 21.
    # Fold 2: Step 21d -> Train Jan 22 - ...
    # So there will be multiple folds.
    # We need to supply data for ALL folds.
    # To simplify, we can set side_effect to return the SAME data for every call.
    # But iter should cycle.
    
    def fetchall_side_effect():
        # returns matrix data, then OOS data...
        while True:
            yield matrix_rows
            yield oos_rows
            
    mock_cursor.fetchall.side_effect = fetchall_side_effect()

    # To fix specific logic verification, we can rely on verifying the aggregation logic
    # which aggregates WHATEVER max_drawdown is returned.
    
    # Mocking require_read_permission
    with patch('trading_platform.api.routers.analytics.require_read_permission') as mock_perm:
        mock_perm.return_value = {"user_id": "test"}
        
        response = client.post(
            "/api/v1/analytics/recommendations/walk-forward/TESTSYM?training_days=90&testing_days=21",
            headers={"Authorization": "Bearer token"}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'success'
    
    folds = data['data']['folds']
    assert len(folds) > 0
    first_fold = folds[0]
    
    # Verify Max Drawdown Calculation
    # Based on our sequence: +100, -200, +50, -300 -> MaxDD 450.
    assert first_fold['max_drawdown_dollars'] == 450.0
    
    # Verify Aggregate Max Drawdown
    aggregate = data['data']['aggregate']
    assert aggregate['max_drawdown'] == 450.0
    
    # Verify Statistically Significant Logic
    # p-value will be calculated by Monte Carlo (random).
    # We set random.seed(42) in the code, so it should be deterministic given the same inputs.
    # But consistency depends on profitable folds.
    # Our data: Total PnL = 100 - 200 + 50 - 300 = -350.
    # Profitable = False.
    # Consistency = 0% (if all folds are same).
    # So Recommendation should be "Strategy requires more data..."
    # And statistically_significant should be False.
    
    assert aggregate['recommendation'] == "Strategy requires more data or parameter tuning — OOS results not yet significant."
    assert aggregate['statistically_significant'] is False

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
