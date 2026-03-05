"""
Test wipe+reimport and 90% SC match verification helpers.

Run: python -m pytest tests/test_wipe_reimport_verify.py -v
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Import after path is set
from run_wipe_reimport_and_verify import (
    get_sc_trade_count,
    get_sc_trade_count_from_activity_export,
    get_db_trade_count,
    get_db_path,
    MIN_MATCH_PCT,
)


class TestSCReferenceCount:
    """Test SC trade count from reference files."""

    def test_activity_export_v_sim16(self):
        """Count closed trades from ALLTradeActivityLogExport (Fills + OpenClose=Close)."""
        path = os.path.join(ROOT, "ALLTradeActivityLogExport_vsim16 11052025-12192025.txt")
        if not os.path.isfile(path):
            pytest.skip("ALLTradeActivityLogExport file not in repo")
        n, _min, _max = get_sc_trade_count_from_activity_export(path, "V_SIM16")
        assert n > 0, "Expected at least one Close fill for V_SIM16"
        assert _min and _max, "Expected date range from export"

    def test_get_sc_trade_count_detects_activity_format(self):
        """get_sc_trade_count detects Activity export and returns (count, min_date, max_date)."""
        path = os.path.join(ROOT, "ALLTradeActivityLogExport_vsim16 11052025-12192025.txt")
        if not os.path.isfile(path):
            pytest.skip("ALLTradeActivityLogExport file not in repo")
        n, _min, _max = get_sc_trade_count(path, "V_SIM16")
        assert n > 0
        assert _min and _max

    def test_match_formula_90_percent(self):
        """Match % = min(db,sc)/max(db,sc)*100; pass when >= 90%."""
        # If DB has 900 and SC has 1000, match = 90%
        match = min(900, 1000) / max(900, 1000) * 100.0
        assert match == 90.0
        assert match >= MIN_MATCH_PCT
        # If DB has 800 and SC has 1000, match = 80%
        match2 = min(800, 1000) / max(800, 1000) * 100.0
        assert match2 == 80.0
        assert match2 < MIN_MATCH_PCT
