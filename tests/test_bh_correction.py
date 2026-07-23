"""
Unit tests for the Benjamini-Hochberg FDR correction function.

Tests verify:
  - Known-good results against hand-calculated expected values
  - Monotonicity (adjusted_p >= raw_p always)
  - None pass-through (slots with insufficient data)
  - Edge cases: single value, all significant, all non-significant
  - Output length equals input length
  - adjusted_p_value is always in [0, 1]

Run with:
    pytest tests/test_bh_correction.py -v
"""

import pytest
from typing import List, Optional

# The module under test
from trading_platform.services.time_bin_analyzer import benjamini_hochberg


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _significant(adjusted: List[Optional[float]], alpha: float = 0.05) -> List[bool]:
    """Return a bool list: True where adjusted value passes FDR threshold."""
    return [
        (q is not None and q <= alpha)
        for q in adjusted
    ]


# ---------------------------------------------------------------------------
# Test 1: Known-good hand-calculated case
#
# m=5 p-values. Sorted ascending: 0.001, 0.01, 0.04, 0.15, 0.50
# BH thresholds at alpha=0.05: rank/m*0.05 => 0.01, 0.02, 0.03, 0.04, 0.05
# p_(1)=0.001 <= 0.010  -> passes
# p_(2)=0.010 <= 0.020  -> passes
# p_(3)=0.040 <= 0.030  -> FAILS
# p_(4)=0.150 <= 0.040  -> FAILS
# p_(5)=0.500 <= 0.050  -> FAILS
# Largest k that passes: k=2. Tests 1 and 2 are significant.
# ---------------------------------------------------------------------------

def test_known_good_case():
    """Two of five p-values should survive BH correction."""
    p_values = [0.04, 0.001, 0.50, 0.15, 0.01]  # unsorted input
    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    assert len(adjusted) == 5, "Output length must equal input length"

    sig = _significant(adjusted)
    # p=0.001 (index 1) and p=0.01 (index 4) should be significant
    # p=0.04 (index 0), p=0.50 (index 2), p=0.15 (index 3) should NOT
    assert sig[1] is True,  "p=0.001 must survive BH correction"
    assert sig[4] is True,  "p=0.010 must survive BH correction"
    assert sig[0] is False, "p=0.040 must NOT survive BH correction (5 tests)"
    assert sig[2] is False, "p=0.500 must NOT survive BH correction"
    assert sig[3] is False, "p=0.150 must NOT survive BH correction"


# ---------------------------------------------------------------------------
# Test 2: All highly significant
# ---------------------------------------------------------------------------

def test_all_significant():
    """When all p-values are tiny, all should survive."""
    p_values = [0.0001, 0.0002, 0.0003, 0.0004, 0.0005]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    sig = _significant(adjusted)
    assert all(sig), "All tiny p-values must survive BH correction"


# ---------------------------------------------------------------------------
# Test 3: None significant
# ---------------------------------------------------------------------------

def test_none_significant():
    """When all p-values are large, none should survive."""
    p_values = [0.5, 0.6, 0.7, 0.8, 0.9]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    sig = _significant(adjusted)
    assert not any(sig), "Large p-values must not survive BH correction"


# ---------------------------------------------------------------------------
# Test 4: Single p-value
# ---------------------------------------------------------------------------

def test_single_p_value_significant():
    """A single small p-value is its own family; it should pass."""
    adjusted = benjamini_hochberg([0.03], alpha=0.05)
    assert len(adjusted) == 1
    assert adjusted[0] is not None
    assert adjusted[0] <= 0.05


def test_single_p_value_not_significant():
    """A single large p-value should not pass."""
    adjusted = benjamini_hochberg([0.20], alpha=0.05)
    assert len(adjusted) == 1
    assert adjusted[0] is not None
    assert adjusted[0] > 0.05


# ---------------------------------------------------------------------------
# Test 5: None pass-through (slots with insufficient data)
# ---------------------------------------------------------------------------

def test_none_pass_through():
    """None entries must remain None in output; valid entries are corrected."""
    p_values = [None, 0.001, None, 0.04, None]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    assert len(adjusted) == 5
    assert adjusted[0] is None, "None input must produce None output at index 0"
    assert adjusted[2] is None, "None input must produce None output at index 2"
    assert adjusted[4] is None, "None input must produce None output at index 4"
    # p=0.001 with m=2 valid tests: threshold = 1/2*0.05=0.025 -> passes
    assert adjusted[1] is not None
    assert adjusted[1] <= 0.05
    # p=0.04 with m=2: threshold = 2/2*0.05=0.05 -> barely passes (0.04 <= 0.05)
    # but after monotonicity enforcement it may be higher than raw
    assert adjusted[3] is not None


def test_all_none():
    """All-None input returns all-None output without crashing."""
    p_values = [None, None, None]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)
    assert adjusted == [None, None, None]


def test_empty_list():
    """Empty input returns empty output."""
    adjusted = benjamini_hochberg([], alpha=0.05)
    assert adjusted == []


# ---------------------------------------------------------------------------
# Test 6: Monotonicity — adjusted_p >= raw_p always
# ---------------------------------------------------------------------------

def test_monotonicity_adjusted_geq_raw():
    """
    For every slot, adjusted_p_value must be >= raw p_value.
    BH can only inflate p-values, never deflate them.
    """
    p_values = [0.001, 0.004, 0.01, 0.02, 0.03, 0.04, 0.05, 0.10, 0.20, 0.50]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    for raw, adj in zip(p_values, adjusted):
        assert adj is not None
        assert adj >= raw - 1e-10, (
            f"Adjusted p={adj:.6f} must not be less than raw p={raw:.6f}"
        )


def test_adjusted_p_in_unit_interval():
    """All adjusted p-values must be in [0, 1]."""
    p_values = [0.001, 0.01, 0.04, 0.15, 0.50]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    for adj in adjusted:
        assert adj is not None
        assert 0.0 <= adj <= 1.0, f"Adjusted p={adj} is outside [0, 1]"


# ---------------------------------------------------------------------------
# Test 7: Output length always equals input length
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 5, 10, 48, 100])
def test_output_length_equals_input(n):
    """Output list length must always match input list length."""
    import random
    p_values = [random.uniform(0, 1) for _ in range(n)]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)
    assert len(adjusted) == n


# ---------------------------------------------------------------------------
# Test 8: 48-slot simulation (real recommendation call size)
# ---------------------------------------------------------------------------

def test_48_slot_family():
    """
    Simulate a full account analysis: 48 time-bin p-values.

    With m=48 tests and alpha=0.05 the BH threshold for rank k is k/48×0.05.
    Rank-5 threshold = 5/48×0.05 ≈ 0.00521, so only p-values well below
    this will survive.  We use 5 signals at 0.0001–0.0005 (all << threshold)
    and 43 noise values drawn from [0.05, 1.0] to mimic a real account run.
    """
    import random
    random.seed(42)

    # 5 genuinely tiny p-values that are safely below the BH rank thresholds
    # BH rank-k threshold with m=48: 1→0.00104, 2→0.00208, 3→0.00313, 4→0.00417, 5→0.00521
    genuine_p = [0.0001, 0.0002, 0.0003, 0.0004, 0.0005]
    noise_p = [random.uniform(0.05, 1.0) for _ in range(43)]
    p_values = genuine_p + noise_p
    random.shuffle(p_values)

    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    raw_sig_count = sum(1 for p in p_values if p < 0.05)
    bh_sig_count = sum(1 for q in adjusted if q is not None and q <= 0.05)

    # BH must retain all 5 genuine signals (p << BH threshold at every rank)
    assert bh_sig_count >= 5, (
        f"BH must retain the 5 genuinely tiny p-values; got bh_sig={bh_sig_count}"
    )
    # BH must never produce MORE significant results than raw testing
    assert bh_sig_count <= raw_sig_count, (
        f"BH must not inflate significant count (bh={bh_sig_count} > raw={raw_sig_count})"
    )



# ---------------------------------------------------------------------------
# Test 9: Identical p-values (edge case for ranking ties)
# ---------------------------------------------------------------------------

def test_identical_p_values():
    """All-equal p-values should be handled without crash."""
    p_values = [0.04, 0.04, 0.04, 0.04, 0.04]
    adjusted = benjamini_hochberg(p_values, alpha=0.05)

    assert len(adjusted) == 5
    for q in adjusted:
        assert q is not None
        assert 0.0 <= q <= 1.0


# ---------------------------------------------------------------------------
# Test 10: Boundary alpha values
# ---------------------------------------------------------------------------

def test_alpha_zero_rejects_everything():
    """With alpha=0, nothing should be significant."""
    p_values = [0.001, 0.002, 0.003]
    adjusted = benjamini_hochberg(p_values, alpha=0.0)
    sig = _significant(adjusted, alpha=0.0)
    assert not any(sig), "alpha=0 must reject all tests"


def test_alpha_one_accepts_everything():
    """With alpha=1, everything should be significant."""
    p_values = [0.1, 0.3, 0.5, 0.8, 0.95]
    adjusted = benjamini_hochberg(p_values, alpha=1.0)
    sig = _significant(adjusted, alpha=1.0)
    assert all(sig), "alpha=1 must accept all tests"
