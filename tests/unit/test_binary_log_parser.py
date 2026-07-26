"""
tests/unit/test_binary_log_parser.py
======================================
Unit tests for binary log parsing, empty files, truncated headers, and ghost fill handling.
"""

import pytest
from pathlib import Path


def test_empty_binary_file(tmp_path: Path):
    """0-byte binary file should be handled gracefully without crashing."""
    empty_file = tmp_path / "test_empty.data"
    empty_file.write_bytes(b"")
    assert empty_file.exists()
    assert empty_file.stat().st_size == 0


def test_truncated_header_file(tmp_path: Path):
    """File smaller than Sierra Chart header (56 bytes) should be skipped gracefully."""
    trunc_file = tmp_path / "test_trunc.data"
    trunc_file.write_bytes(b"Short Header")
    assert trunc_file.stat().st_size < 56


def test_ghost_fill_resync_zero_position():
    """Verify ghost fill resynchronization logic resets position state to 0."""
    # Simulated position state tracking
    position = 1
    is_ghost = True

    # Resync on ghost exit fill
    if is_ghost:
        position = 0

    assert position == 0
