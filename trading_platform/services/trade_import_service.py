"""
Trade Import Service — parses copy-pasted Sierra Chart TradesList.txt data
and inserts only missing trades into the database.

The pasted format is the 26-column tab-delimited "Period Stats" export
from Sierra Chart.  The Account/permutation name lives in the Note column.
"""

import logging
import sqlite3
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Data models
# ──────────────────────────────────────────────────────────────

@dataclass
class ParsedTrade:
    """A single trade parsed from pasted text."""
    symbol: str
    trade_type: str         # Long / Short
    entry_datetime: datetime
    entry_price: float
    exit_datetime: datetime
    exit_price: float
    quantity: int
    max_open_quantity: int
    max_closed_quantity: int
    profit_loss: float
    cumulative_pnl: float
    commission: float
    flat_to_flat_pnl: float
    note: str               # Contains the permutation/account name
    flat_to_flat_max_profit: float
    flat_to_flat_max_loss: float
    max_open_profit: float
    max_open_loss: float
    entry_efficiency: str
    exit_efficiency: str
    total_efficiency: str
    high_while_open: float
    low_while_open: float
    open_position_quantity: int
    close_position_quantity: int
    duration: str
    # Derived
    account_name: str = ""
    base_symbol: str = ""


@dataclass
class ImportResult:
    """Summary of an import operation."""
    total_parsed: int = 0
    new_trades: int = 0
    duplicates: int = 0
    errors: List[str] = field(default_factory=list)
    parsed_trades: List[ParsedTrade] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Expected header (26 columns)
# ──────────────────────────────────────────────────────────────

EXPECTED_HEADERS = [
    "Symbol", "Trade Type", "Entry DateTime", "Entry Price",
    "Exit DateTime", "Exit Price", "Trade Quantity",
    "Max Open Quantity", "Max Closed Quantity",
    "Profit/Loss (C)", "Cumulative Profit/Loss (C)", "Commission (C)",
    "FlatToFlat Profit/Loss (C)", "Note",
    "FlatToFlat Max Open Profit (C)", "FlatToFlat Max Open Loss (C)",
    "Max Open Profit (C)", "Max Open Loss (C)",
    "Entry Efficiency", "Exit Efficiency", "Total Efficiency",
    "High Price While Open", "Low Price While Open",
    "Open Position Quantity", "Close Position Quantity", "Duration"
]


# ──────────────────────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────────────────────

class TradeImportService:
    """Parse pasted Sierra Chart trades and insert into the DB."""

    def __init__(self, db_path: str = "trading_platform.db"):
        self.db_path = db_path

    # ── public API ──────────────────────────────────────────
    def preview(self, raw_text: str) -> ImportResult:
        """Parse the text and return a preview (no DB writes)."""
        result = ImportResult()
        lines = self._split_lines(raw_text)
        if not lines:
            return result

        data_lines, header = self._strip_header(lines)
        col_map = self._get_column_map(header)

        # Connect to DB to check for duplicates during preview
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            for idx, line in enumerate(data_lines, start=1):
                try:
                    trade = self._parse_line(line, col_map)
                    if trade:
                        # Check duplicate status
                        is_dup = self._is_duplicate(conn, trade)
                        if is_dup:
                            result.duplicates += 1
                        else:
                            result.new_trades += 1
                            
                        result.parsed_trades.append(trade)
                        result.total_parsed += 1
                except Exception as exc:
                    result.errors.append(f"Line {idx}: {exc}")
        finally:
            conn.close()

        return result

    def import_trades(self, raw_text: str) -> ImportResult:
        """Parse, deduplicate, and insert trades."""
        result = self.preview(raw_text)
        if not result.parsed_trades:
            return result

        # Reset counters — preview already set total_parsed
        result.new_trades = 0
        result.duplicates = 0

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        logger.info(f"Starting import of {len(result.parsed_trades)} trades...")
        
        try:
            for i, trade in enumerate(result.parsed_trades):
                try:
                    if self._is_duplicate(conn, trade):
                        result.duplicates += 1
                    else:
                        self._insert_trade(conn, trade)
                        result.new_trades += 1
                        # Commit every 100 trades to keep things moving
                        if result.new_trades % 100 == 0:
                            conn.commit()
                except Exception as exc:
                    # Individual trade failure
                    error_msg = f"DB error on trade {i+1} ({trade.symbol} {trade.entry_datetime}): {exc}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)
                    # If it's a constraint error, we just count it as an error and continue
                    # But if it's a connection error, we might want to stop
            
            conn.commit() # Final commit
        except Exception as exc:
            conn.rollback()
            result.errors.append(f"Fatal DB error: {exc}")
            logger.error(f"Fatal Import DB error: {exc}", exc_info=True)
        finally:
            conn.close()

        logger.info(
            f"Import complete: {result.new_trades} new, "
            f"{result.duplicates} duplicates, {len(result.errors)} errors"
        )
        return result

    # ── parsing helpers ─────────────────────────────────────

    @staticmethod
    def _split_lines(raw_text: str) -> List[str]:
        """Split raw text, stripping empties."""
        return [l for l in raw_text.replace('\r\n', '\n').split('\n') if l.strip()]

    @staticmethod
    def _strip_header(lines: List[str]) -> Tuple[List[str], Optional[str]]:
        """Remove header row if present. Returns (data_lines, header_row)."""
        if not lines:
            return lines, None
        first_fields = lines[0].split('\t')
        # Header detection: first field is literally "Symbol"
        if first_fields[0].strip().lower() == "symbol":
            return lines[1:], lines[0]
        return lines, None

    def _get_column_map(self, header_row: Optional[str]) -> Dict[str, int]:
        """Map header names to column indices."""
        # Default mapping (fallback if no header)
        mapping = {
            "symbol": 0,
            "trade_type": 1,
            "entry_datetime": 2,
            "entry_price": 3,
            "exit_datetime": 4,
            "exit_price": 5,
            "quantity": 6,
            "profit_loss": 9,
            "commission": 11,
            "note": 13,
            "duration": 25,
        }

        if not header_row:
            return mapping

        header_fields = [f.strip().lower() for f in header_row.split('\t')]
        
        # Helper to find index by partial match
        def find_idx(patterns: List[str]) -> Optional[int]:
            for i, field in enumerate(header_fields):
                for p in patterns:
                    if p in field:
                        return i
            return None

        # Dynamically detect columns
        new_mapping = {}
        new_mapping["symbol"] = find_idx(["symbol"])
        new_mapping["trade_type"] = find_idx(["trade type"])
        new_mapping["entry_datetime"] = find_idx(["entry datetime"])
        new_mapping["exit_datetime"] = find_idx(["exit datetime"])
        new_mapping["entry_price"] = find_idx(["entry price"])
        new_mapping["exit_price"] = find_idx(["exit price"])
        new_mapping["quantity"] = find_idx(["trade quantity", "quantity"])
        new_mapping["profit_loss"] = find_idx(["profit/loss (c)", "profit/loss", "p/l"])
        new_mapping["commission"] = find_idx(["commission (c)", "commission"])
        new_mapping["note"] = find_idx(["note"])
        new_mapping["duration"] = find_idx(["duration"])
        new_mapping["account"] = find_idx(["account"]) # Optional account override

        # Merge - keep defaults if dynamic detection failed for a specific key
        for key, val in new_mapping.items():
            if val is not None:
                mapping[key] = val
                
        return mapping

    def _parse_line(self, line: str, col_map: Dict[str, int]) -> Optional[ParsedTrade]:
        """Parse a single tab-delimited line into a ParsedTrade using a column map."""
        fields = line.split('\t')
        
        # Max index needed
        max_idx = max(col_map.values())
        if len(fields) <= max_idx:
             raise ValueError(f"Line has {len(fields)} columns, but needs index {max_idx}")

        # Extract values using the map
        def get_field(key: str, default: str = "") -> str:
            idx = col_map.get(key)
            return fields[idx].strip() if idx is not None and idx < len(fields) else default

        entry_dt = self._parse_dt(get_field("entry_datetime"))
        exit_dt = self._parse_dt(get_field("exit_datetime"))

        if entry_dt is None:
             raise ValueError(f"Incomplete trade: Missing Entry DateTime '{get_field('entry_datetime')}'")
        if exit_dt is None:
             raise ValueError(f"Skipping Open Position: Missing Exit DateTime '{get_field('exit_datetime')}'")

        trade = ParsedTrade(
            symbol=get_field("symbol"),
            trade_type=get_field("trade_type"),
            entry_datetime=entry_dt,
            entry_price=self._parse_float(get_field("entry_price")),
            exit_datetime=exit_dt,
            exit_price=self._parse_float(get_field("exit_price")),
            quantity=self._parse_int(get_field("quantity")),
            # These were added for completeness but might not be in all exports
            max_open_quantity=0, 
            max_closed_quantity=0,
            profit_loss=self._parse_float(get_field("profit_loss")),
            cumulative_pnl=0.0,
            commission=self._parse_float(get_field("commission")),
            flat_to_flat_pnl=0.0,
            note=get_field("note"),
            flat_to_flat_max_profit=0.0,
            flat_to_flat_max_loss=0.0,
            max_open_profit=0.0,
            max_open_loss=0.0,
            entry_efficiency="",
            exit_efficiency="",
            total_efficiency="",
            high_while_open=0.0,
            low_while_open=0.0,
            open_position_quantity=0,
            close_position_quantity=0,
            duration=get_field("duration"),
        )
        
        # Derive account name
        sc_account = get_field("account")
        if sc_account:
             trade.account_name = sc_account
        else:
             trade.account_name = self._extract_account_name(trade.note)

        # Derive base symbol
        trade.base_symbol = self._extract_base_symbol(trade.symbol)
        
        # Smart Naming: If the account name starts with the symbol (e.g. CL_PB1) and it's redundant, strip it
        # But be careful not to strip if it's just a coincidence. 
        # Heuristic: Symbol + "_" or Symbol + "-" at start.
        if trade.base_symbol:
            prefix_underscore = f"{trade.base_symbol}_"
            prefix_hyphen = f"{trade.base_symbol}-"
            
            if trade.account_name.startswith(prefix_underscore):
                trade.account_name = trade.account_name[len(prefix_underscore):]
            elif trade.account_name.startswith(prefix_hyphen):
                trade.account_name = trade.account_name[len(prefix_hyphen):]
                
        return trade


    # ── field-level parsers ─────────────────────────────────

    @staticmethod
    def _parse_dt(value: str) -> Optional[datetime]:
        """Parse datetime, stripping BP/EP markers. Returns None if empty/invalid."""
        v = value.strip()
        if not v:
            return None
        # Remove Sierra Chart markers
        v = v.replace(" BP", "").replace(" EP", "").strip()
        # Collapse multiple spaces
        while "  " in v:
            v = v.replace("  ", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(v, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_float(value: str) -> float:
        v = value.strip()
        if not v:
            return 0.0
        # Remove trailing " F" (flat-to-flat marker) and % signs
        if v.endswith(" F"):
            v = v[:-2]
        v = v.replace("%", "").replace(",", "")
        return float(v)

    @staticmethod
    def _parse_int(value: str) -> int:
        v = value.strip()
        if not v:
            return 0
        if v.endswith(" F"):
            v = v[:-2]
        v = v.replace("%", "")
        return int(float(v))

    @staticmethod
    def _extract_account_name(note: str) -> str:
        """
        The Note field IS the account/permutation identifier.
        We use the full Note value as the account name.
        """
        return note.strip() if note else "UNKNOWN"

    @staticmethod
    def _extract_base_symbol(symbol: str) -> str:
        """Extract base symbol: F.US.MNQH23 → MNQ, NQH24 → NQ, etc."""
        s = symbol.strip()
        # Handle F.US.XXX format  →  strip prefix
        if s.startswith("F.US."):
            s = s[5:]  # e.g. "MNQH23 (105484)" or "MNQH23"
        # Strip parenthesized exchange ID
        s = re.sub(r'\s*\(.*?\)', '', s).strip()
        # Now extract letters-only prefix (stop at first digit or month code)
        if s.startswith("MNQ"):
            return "MNQ"
        if s.startswith("NQ"):
            return "NQ"
        if s.startswith("FDAX"):
            return "FDAX"
        if s.startswith("ES"):
            return "ES"
        if s.startswith("CL"):
            return "CL"
        # Generic fallback — letters before digits
        match = re.match(r'([A-Z]+)', s)
        return match.group(1) if match else s

    # ── dedup / DB helpers ──────────────────────────────────

    @staticmethod
    def _is_duplicate(conn: sqlite3.Connection, trade: ParsedTrade) -> bool:
        """Check if a matching trade already exists in processed_trades."""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM processed_trades
            WHERE account_name = ?
              AND symbol = ?
              AND entry_time = ?
              AND entry_price = ?
              AND exit_time = ?
              AND exit_price = ?
              AND profit_loss = ?
            LIMIT 1
            """,
            (
                trade.account_name,
                trade.base_symbol,
                trade.entry_datetime.isoformat(),
                trade.entry_price,
                trade.exit_datetime.isoformat(),
                trade.exit_price,
                trade.profit_loss,
            ),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _insert_trade(conn: sqlite3.Connection, trade: ParsedTrade) -> None:
        """Insert a parsed trade into processed_trades."""
        side = "LONG" if trade.trade_type.upper() in ("LONG", "BUY") else "SHORT"
        duration_minutes = int(
            (trade.exit_datetime - trade.entry_datetime).total_seconds() / 60
        )
        # Deterministic trade_id
        # We use a string that unique identifies the trade context
        trade_id = (
            f"{trade.account_name}_{trade.base_symbol}_"
            f"{trade.entry_datetime.strftime('%Y%m%d_%H%M%S')}_"
            f"{trade.exit_datetime.strftime('%Y%m%d_%H%M%S')}_"
            f"{int(trade.entry_price * 100)}_{int(trade.exit_price * 100)}_"
            f"{trade.quantity}_{int(trade.profit_loss * 100)}"
        )

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO processed_trades (
                trade_id, account_name, symbol,
                entry_time, exit_time,
                entry_price, exit_price,
                quantity, side, profit_loss, commission,
                duration_minutes, hour_of_day, day_of_week
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                trade.account_name,
                trade.base_symbol,
                trade.entry_datetime.isoformat(),
                trade.exit_datetime.isoformat(),
                trade.entry_price,
                trade.exit_price,
                trade.quantity,
                side,
                trade.profit_loss,
                trade.commission,
                duration_minutes,
                trade.entry_datetime.hour,
                trade.entry_datetime.weekday(),
            ),
        )
