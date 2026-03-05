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
from ..utils.timezone_utils import to_ny
from .binary_log_parser import SYMBOL_METADATA

logger = logging.getLogger(__name__)


def _base_symbol(sym: str) -> str:
    s = sym.upper()
    for base in list(SYMBOL_METADATA.keys()) + ["NQ", "ES", "CL"]:
        if s.startswith(base):
            return base
    return s[:2] if len(s) >= 2 else s


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
    rejected_trades: List[Dict[str, Any]] = field(default_factory=list)
    dropped_ghost_fills: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


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

    def _pairs_by_open_close(self, fills: List[Dict]) -> Tuple[List[Dict], int]:
        """
        Pair Open with Close by ParentInternalOrderID when available; else FIFO.
        SC-exact when ParentInternalOrderID is populated; FIFO fallback when empty.
        Returns (trades, unpaired_count).
        """
        from collections import defaultdict
        groups = defaultdict(list)
        for f in fills:
            key = (f['account_name'], f['symbol'])
            groups[key].append(f)
        all_trades = []
        unpaired = 0
        for (acc, sym), group in groups.items():
            group.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))
            base_sym = _base_symbol(sym)
            meta = SYMBOL_METADATA.get(base_sym, {"multiplier": 1, "comm": 4.20})
            multiplier = meta["multiplier"]
            comm_per_leg = meta["comm"] / 2.0
            opens = {}  # internal_order_id -> list of {fill, qty_left}
            opens_fifo = []  # [(fill, qty_left), ...] for FIFO when parent empty
            for f in group:
                oc = (f.get("open_close") or "").upper()
                oid = (f.get("internal_order_id") or "").strip()
                parent = (f.get("parent_order_id") or "").strip()
                if oc == "OPEN" and oid:
                    if oid not in opens:
                        opens[oid] = []
                    entry = {"fill": f, "qty_left": f["quantity"]}
                    opens[oid].append(entry)
                    opens_fifo.append(entry)
                elif oc == "CLOSE":
                    close_qty = f["quantity"]
                    matched = False
                    if parent and parent in opens and opens[parent]:
                        entry_list = opens[parent]
                        while close_qty > 0 and entry_list:
                            o = entry_list[0]
                            match_qty = min(close_qty, o["qty_left"])
                            if match_qty <= 0:
                                entry_list.pop(0)
                                continue
                            of = o["fill"]
                            pnl = (f["price"] - of["price"]) * match_qty * multiplier if of["side"] in ("BUY", "LONG") else (of["price"] - f["price"]) * match_qty * multiplier
                            total_comm = round(match_qty * (comm_per_leg * 2), 2)
                            side = "LONG" if of["side"] in ("BUY", "LONG") else "SHORT"
                            all_trades.append({
                                "account": acc, "symbol": base_sym, "side": side,
                                "entry_time": of["timestamp"], "exit_time": f["timestamp"],
                                "entry_price": of["price"], "exit_price": f["price"],
                                "quantity": int(match_qty), "profit_loss": round(pnl - total_comm, 2),
                                "commission": total_comm
                            })
                            o["qty_left"] -= match_qty
                            close_qty -= match_qty
                            if o["qty_left"] <= 0:
                                entry_list.pop(0)
                            matched = True
                        if not opens[parent]:
                            del opens[parent]
                    if close_qty > 0 and opens_fifo:
                        f_side = (f.get("side") or "").upper()
                        want_open_side = "SELL" if f_side in ("BUY", "LONG") else "BUY"
                        i = 0
                        while close_qty > 0 and i < len(opens_fifo):
                            o = opens_fifo[i]
                            of = o["fill"]
                            if o["qty_left"] <= 0:
                                i += 1
                                continue
                            of_side = (of.get("side") or "").upper()
                            if of_side != want_open_side:
                                i += 1
                                continue
                            match_qty = min(close_qty, o["qty_left"])
                            if match_qty <= 0:
                                i += 1
                                continue
                            pnl = (f["price"] - of["price"]) * match_qty * multiplier if of_side in ("BUY", "LONG") else (of["price"] - f["price"]) * match_qty * multiplier
                            total_comm = round(match_qty * (comm_per_leg * 2), 2)
                            side = "LONG" if of_side in ("BUY", "LONG") else "SHORT"
                            all_trades.append({
                                "account": acc, "symbol": base_sym, "side": side,
                                "entry_time": of["timestamp"], "exit_time": f["timestamp"],
                                "entry_price": of["price"], "exit_price": f["price"],
                                "quantity": int(match_qty), "profit_loss": round(pnl - total_comm, 2),
                                "commission": total_comm
                            })
                            o["qty_left"] -= match_qty
                            close_qty -= match_qty
                            matched = True
                            if o["qty_left"] <= 0:
                                opens_fifo.pop(i)
                            else:
                                i += 1
                        if close_qty > 0:
                            unpaired += close_qty
                    elif close_qty > 0 and not matched:
                        unpaired += close_qty
            opens_fifo[:] = [o for o in opens_fifo if o["qty_left"] > 0]
            unpaired += sum(o["qty_left"] for o in opens_fifo)
            unpaired += sum(sum(x["qty_left"] for x in v) for v in opens.values())
        return all_trades, int(unpaired)

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
                        # Detect potential Ghost Trades (from Sierra aggregation bug)
                        # but DO NOT reject them. We want them in the DB for reconciliation.
                        max_q = getattr(trade, 'max_open_quantity', 0)
                        if max_q > 3:
                            warning_msg = f"Sierra Aggregation Detected: {trade.account_name} has Max Qty {max_q} at {trade.entry_datetime}. This is likely a lumped trade."
                            if warning_msg not in result.errors:
                                result.errors.append(warning_msg)

                        # Check duplicate status
                        is_dup = self._is_duplicate(conn, trade)
                        if is_dup:
                            result.duplicates += 1
                        else:
                            result.new_trades += 1
                            
                        result.parsed_trades.append(trade)
                        result.total_parsed += 1
                except Exception as e:
                    result.errors.append(f"Line {idx}: {e}")
        finally:
            conn.close()

        return result

    def import_trades(self, raw_text: str) -> ImportResult:
        """Parse, deduplicate, and insert trades."""
        # Detect Format
        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        header_lower = (lines[0] if lines else "").lower()
        for line in lines[:5]:
            if line.startswith("Fills"):
                return self._import_activity_log(raw_text)
        # ALLTradeActivityLogExport: ActivityType, OpenClose columns
        if "activitytype" in header_lower and "openclose" in header_lower:
            return self._import_activity_log(raw_text)

        result = self.preview(raw_text)
        if not result.parsed_trades:
            return result

        # Reset counters — preview already set total_parsed
        result.new_trades = 0
        result.duplicates = 0

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        logger.info(f"Starting import of {len(result.parsed_trades)} trades...")
        
        touched_accounts = set()
        
        try:
            for i, trade in enumerate(result.parsed_trades):
                touched_accounts.add(trade.account_name)
                try:
                    if self._is_duplicate(conn, trade):
                        result.duplicates += 1
                    else:
                        self._insert_trade(conn, trade)
                        result.new_trades += 1
                        if result.new_trades % 100 == 0:
                            conn.commit()
                except Exception as exc:
                    error_msg = f"DB error on trade {i+1} ({trade.symbol} {trade.entry_datetime}): {exc}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)
            
            conn.commit()
            
            # AUTO-PURGE DISABLED: We no longer automatically delete trades after import.
            # This allows users to see their data first. If they want to clean it, 
            # they can use the 'Purge' functionality in the UI.
            full_stats = {}
            # for acc in touched_accounts:
            #     breakdown = parser.purge_anomalies(account=acc, purge_overnight=True)
            #     full_stats.update(breakdown)
                
            result.stats = full_stats

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

    def _import_activity_log(self, text: str) -> ImportResult:
        """Special handler for raw Activity Log (Fills) paste."""
        from .binary_log_parser import BinaryLogParser
        import re
        from datetime import datetime
        
        parser = BinaryLogParser(self.db_path)
        
        result = ImportResult()
        fills = []
        lines_text = [l for l in text.replace('\r\n', '\n').split('\n') if l.strip()]
        if not lines_text:
            return result
            
        header_fields = [f.strip().lower() for f in lines_text[0].split('\t')]
        # Detect any common header indicators
        has_header = any(h in header_fields for h in [
            "datetime", "time", "dt_entry", "dtentry", 
            "tradeaccount", "account", "acc",
            "symbol", "ticker", "instrument",
            "fillprice", "price", "avgprice"
        ])
        data_lines = lines_text[1:] if has_header else lines_text
        
        if not has_header:
            # Matches standard SC Activity Log copy-paste: 14 columns
            header_fields = ["activity_type", "dt_entry", "dt_proc", "order_id", "order_type", "order_qty", "order_status", "account", "side", "price1", "price2", "fill_price", "fill_qty", "note"]
            
        def find_idx(patterns):
            # Try patterns in order (most specific first) so "fillprice" matches before "price"
            for p in patterns:
                for i, field in enumerate(header_fields):
                    if p in field:
                        return i
            return None

        col_map = {
            "datetime": find_idx(["datetime", "time", "dt_entry", "dtentry", "timestamp"]),
            "account": find_idx(["tradeaccount", "account", "acc", "name"]),
            "side": find_idx(["buysell", "side", "direction"]),  # omit "type" - matches "activitytype"
            "fillprice": find_idx(["fillprice", "fill_price", "avgprice", "avgfill", "price"]),
            "filledquan": find_idx(["filledquantity", "filledquan", "fill_qty", "quantity", "qty", "amount"]),
            "orderstatus": find_idx(["order_status", "orderstatus", "status"]),
            "symbol": find_idx(["symbol", "ticker", "instrument", "contract"]),
            "note": find_idx(["note", "text", "tag", "description"]),
            "openclose": find_idx(["openclose", "open_close"]),
            "internalorderid": find_idx(["internalorderid", "internal_order_id", "order_id"]),
            "parentorderid": find_idx(["parentinternalorderid", "parent_internal_order_id"]),
            "activitytype": find_idx(["activitytype", "activity_type"]),
        }
        
        for idx, line in enumerate(data_lines):
            # Support both tabs and multiple spaces as delimiters
            parts = line.split('\t')
            if len(parts) < 3 and '  ' in line:
                parts = [p.strip() for p in re.split(r'  +', line) if p.strip()]
            
            if len(parts) < 3:
                 continue

            # Dynamic Column Mapping for Activity Log (if no header)
            # Sierra Chart Activity Logs vary between 11, 12, and 14 columns.
            current_col_map = col_map.copy()
            if not has_header and parts[0].strip() == "Fills":
                if 10 <= len(parts) <= 12:
                    # 11/12 column layout: [0]Type, [4]OrderType, [6]Status, [7]Account, [8]Side, [9]FillPrice, [10]FillQty, [11]Note
                    current_col_map["orderstatus"] = 6
                    current_col_map["account"] = 7
                    current_col_map["side"] = 8
                    current_col_map["fillprice"] = 9
                    current_col_map["filledquan"] = 10
                    current_col_map["note"] = 11 if len(parts) > 11 else 10
                elif len(parts) >= 13:
                    # 14 column layout: [11]FillPrice, [12]FillQty, [13]Note
                    current_col_map["fillprice"] = 11
                    current_col_map["filledquan"] = 12
                    current_col_map["note"] = 13 if len(parts) > 13 else 12
            
            try:
                def get_field(key): 
                    idx = current_col_map.get(key)
                    return parts[idx].strip() if idx is not None and idx < len(parts) else ""
                
                # Filter for FILLED status
                status = get_field("orderstatus").upper()
                if status != "FILLED":
                    continue
                # Filter ActivityType: only Fills (ALLTradeActivityLogExport has ActivityType column)
                at_val = get_field("activitytype")
                if at_val and at_val.lower() != "fills":
                    continue
                # No header: enforce "Fills" prefix
                if not has_header:
                    if parts[0].strip() != "Fills" and "Fills" not in parts[0]:
                        continue
                
                
                dt_str = get_field("datetime")
                acc = get_field("account")
                side = get_field("side").upper()
                # Robust Side Detection: If 'side' column is empty or non-standard, scan entire row
                if side not in ("BUY", "SELL", "LONG", "SHORT"):
                    found_side = None
                    for p_raw in parts:
                        p_up = p_raw.strip().upper()
                        if p_up in ("BUY", "SELL", "LONG", "SHORT"):
                            found_side = p_up
                            break
                    if found_side: 
                        side = found_side
                
                price_str = get_field("fillprice")
                qty_str = get_field("filledquan")
                note_str = get_field("note")

                if not dt_str or not side or not price_str or not qty_str: continue
                
                try: 
                    price = float(price_str)
                    qty = int(float(qty_str))
                except ValueError: 
                    continue
                if qty <= 0: continue
                
                # Ultimate Symbol Extraction
                symbol = get_field("symbol") # Try detected column first
                if not symbol or symbol == "" or symbol.upper() == "UNKNOWN":
                    # Fallback: Scan all fields in the row 
                    for p_raw in parts:
                        p_clean = p_raw.strip()
                        # Try contract pattern NQH26
                        m = re.search(r'\b([A-Z]{1,3}[HMUZ]\d{1,2})\b', p_clean, re.I)
                        if m:
                            symbol = m.group(1).upper()
                            break
                        # Try AT_ pattern
                        m = re.search(r'AT_([A-Z]+)', p_clean, re.I)
                        if m:
                            symbol = m.group(1).upper()
                            break
                if not symbol: symbol = "UNKNOWN"
                        
                ts_val = 0
                parsed_dt = None
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        parsed_dt = datetime.strptime(dt_str, fmt)
                        ts_val = parsed_dt.timestamp()
                        break
                    except ValueError: continue
                if not parsed_dt: continue
                    
                openclose = get_field("openclose").strip()
                internal_oid = get_field("internalorderid") or get_field("parentorderid") or ""
                parent_oid = get_field("parentorderid") or internal_oid
                fills.append({
                    "timestamp": parsed_dt.isoformat(), "ts_val": ts_val, "account_name": acc.upper(), "side": side,
                    "price": price, "quantity": qty, "symbol": symbol.upper(), "order_id": internal_oid or "PASTE",
                    "source": "PASTE", "offset": idx,
                    "open_close": openclose.upper() if openclose else "",
                    "internal_order_id": internal_oid, "parent_order_id": parent_oid,
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to parse Fills line {idx}: {e}")

        if not fills:
            return result

        # --- RESET STUCK POSITIONS ---
        # Before processing a manual paste, we clear any 'ghost' pending fills 
        # to ensure we don't carry forward errors from previous failed attempts.
        unique_accs = list(set(f['account_name'] for f in fills))
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            for acc_name in unique_accs:
                cursor.execute("DELETE FROM pending_fills WHERE account_name = ?", (acc_name,))
            conn.commit()
        finally:
            conn.close()

        fills.sort(key=lambda x: (x['timestamp'], x['offset']))

        # Use Open/Close pairing when available (SC-exact matching)
        fills_with_oc = [f for f in fills if f.get('open_close') in ('OPEN', 'CLOSE')]
        if len(fills_with_oc) >= 2 and len(fills_with_oc) >= len(fills) * 0.5:
            trades, unpaired_count = self._pairs_by_open_close(fills_with_oc)
            position_warnings = {}
        else:
            # Strip Open/Close keys for FIFO (binary parser expects plain fills)
            for f in fills:
                f.pop('open_close', None)
                f.pop('internal_order_id', None)
                f.pop('parent_order_id', None)
            trades, unpaired_count, position_warnings = parser._pairs_to_trades(fills)
        dropped_ghost_fills = getattr(parser, 'ghost_list', [])
        
        if unpaired_count > 0:
            result.stats['unpaired'] = {
                "count": unpaired_count,
                "commission_impact": round(unpaired_count * 2.10, 2)
            }
        
        parsed_objs = []
        for t in trades:
            try:
                entry_utc = datetime.fromisoformat(t['entry_time']) if isinstance(t['entry_time'], str) else t['entry_time']
                exit_utc = datetime.fromisoformat(t['exit_time']) if isinstance(t['exit_time'], str) else t['exit_time']
                
                pt = ParsedTrade(
                    symbol=t['symbol'],
                    trade_type=t['side'],
                    entry_datetime=to_ny(entry_utc),
                    entry_price=t['entry_price'],
                    exit_datetime=to_ny(exit_utc),
                    exit_price=t['exit_price'],
                    quantity=t['quantity'],
                    max_open_quantity=0, max_closed_quantity=0,
                    profit_loss=t['profit_loss'],
                    cumulative_pnl=0,
                    commission=t['commission'],
                    flat_to_flat_pnl=0,
                    note=t['account'],
                    flat_to_flat_max_profit=0, flat_to_flat_max_loss=0,
                    max_open_profit=0, max_open_loss=0,
                    entry_efficiency="", exit_efficiency="", total_efficiency="",
                    high_while_open=0, low_while_open=0,
                    open_position_quantity=0, close_position_quantity=0,
                    duration="",
                    account_name=t['account'].upper(),
                    base_symbol=t['symbol'].upper()
                )
                parsed_objs.append(pt)
            except Exception as e:
                result.errors.append(f"Conversion error: {e}")

        result.parsed_trades = parsed_objs
        result.total_parsed = len(fills) # Count raw fills seen
        result.stats['fills_count'] = len(fills)
        result.stats['trades_closed'] = len(parsed_objs)

        if not parsed_objs and unpaired_count > 0:
            result.errors.append(f"Parsed {len(fills)} fills, but they haven't formed any closed trades yet (Stored as {unpaired_count} unpaired executions in memory).")

        result.dropped_ghost_fills = dropped_ghost_fills
        
        conn = sqlite3.connect(self.db_path)
        touched = set()
        try:
            # AUTO-CLEANUP: If importing high-integrity Fills, overwrite any existing trades in this specific window.
            if parsed_objs:
                min_t = min(pt.entry_datetime for pt in parsed_objs).isoformat()
                max_t = max(pt.exit_datetime for pt in parsed_objs).isoformat()
                unique_accs = list(set(pt.account_name for pt in parsed_objs))
                
                cursor = conn.cursor()
                total_wiped = 0
                for acc_name in unique_accs:
                    cursor.execute(
                        "DELETE FROM processed_trades WHERE account_name = ? AND entry_time >= ? AND exit_time <= ?",
                        (acc_name, min_t, max_t)
                    )
                    total_wiped += cursor.rowcount
                
                if total_wiped > 0:
                    import logging
                    logging.getLogger(__name__).info(f"Auto-cleaned {total_wiped} overlapping trades to prevent double-counting.")
                    result.stats['auto_cleaned_count'] = total_wiped

            for pt in parsed_objs:
                touched.add(pt.account_name)
                # Ensure _is_duplicate is accessible via self
                if self._is_duplicate(conn, pt):
                    result.duplicates += 1
                else:
                    self._insert_trade(conn, pt)
                    result.new_trades += 1
            conn.commit()
            
            # AUTO-PURGE DISABLED: We no longer automatically delete trades after import.
            full_stats = {}
            # for acc in touched:
            #     breakdown = parser.purge_anomalies(account=acc, purge_overnight=True)
            #     full_stats.update(breakdown)
            result.stats.update(full_stats)
            
        finally:
            conn.close()
            
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
             trade.account_name = sc_account.upper()
        else:
             trade.account_name = self._extract_account_name(trade.note).upper()

        # Derive base symbol
        trade.base_symbol = self._extract_base_symbol(trade.symbol).upper()
        
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
        
        # Remove Sierra Chart markers (BP/EP) robustly using regex
        # Handles " EP", "  EP", "BP", etc. at end of string
        v = re.sub(r'\s*[BE]P$', '', v, flags=re.IGNORECASE).strip()
        
        # Collapse multiple spaces
        v = re.sub(r'\s+', ' ', v)
        
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
        return note.strip().upper() if note else "UNKNOWN"

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
        return match.group(1).upper() if match else s.upper()

    # ── dedup / DB helpers ──────────────────────────────────

    @staticmethod
    def _generate_trade_id(trade: ParsedTrade) -> str:
        """Generate a deterministic trade_id with microsecond precision."""
        return (
            f"{trade.account_name}_{trade.base_symbol}_"
            f"{trade.entry_datetime.strftime('%Y%m%d_%H%M%S_%f')}_"
            f"{trade.exit_datetime.strftime('%Y%m%d_%H%M%S_%f')}_"
            f"{int(trade.entry_price * 100)}_{int(trade.exit_price * 100)}_"
            f"{trade.quantity}_{int(trade.profit_loss * 100)}"
        )

    @staticmethod
    def _is_duplicate(conn: sqlite3.Connection, trade: ParsedTrade) -> bool:
        """Check if a matching trade already exists in processed_trades using trade_id."""
        cursor = conn.cursor()
        trade_id = TradeImportService._generate_trade_id(trade)
        cursor.execute(
            "SELECT 1 FROM processed_trades WHERE trade_id = ? LIMIT 1",
            (trade_id,)
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
        trade_id = TradeImportService._generate_trade_id(trade)

        # Convert entry time to NY for session stats
        entry_ny = to_ny(trade.entry_datetime)
        
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO processed_trades (
                trade_id, account_name, symbol,
                entry_time, exit_time,
                entry_price, exit_price,
                quantity, side, profit_loss, commission,
                duration_minutes, hour_of_day, day_of_week
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                trade.account_name.upper(),
                trade.base_symbol.upper(),
                trade.entry_datetime.isoformat(),
                trade.exit_datetime.isoformat(),
                trade.entry_price,
                trade.exit_price,
                trade.quantity,
                side,
                trade.profit_loss,
                trade.commission,
                duration_minutes,
                entry_ny.hour,
                entry_ny.weekday(),
            ),
        )
