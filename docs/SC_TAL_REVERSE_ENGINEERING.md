# Sierra Chart Trade Activity Log — Reverse Engineering Summary

## 1. Official Documentation (sierrachart.com)

### File Format
- **Location:** `TradeActivityLogs` subfolder in SC installation
- **Filename:** `TradeActivityLog_YYYY-MM-DD_UTC.[TradeAccount].data` (or `.simulated.data`)
- **Time range:** 00:00:00–23:59:59 **UTC** per file (per SC support)
- **Format:** Proprietary binary — **no official spec published**. SC Support (Thread 100015): "We could add an ACSIL function to do Trade Activity Log to text file exports" — not yet done.

### How SC Builds the Trades Tab
From [Trade Activity Log](https://www.sierrachart.com/index.php?page=doc/TradeActivityLog.php):

1. **Source:** Trade Activity tab = raw records (Orders, Fills, Positions). Trades tab = **computed** from fills.
2. **Fill matching:** `Edit >> Use Last In First Out Fill Matching` — default is **FIFO** (unchecked = FIFO).
3. **Flat to Flat:** `Edit >> Flat to Flat Display for Trades List` — groups sub-trades into flat-to-flat sequences.
4. **From Date:** Must start at a point where position was **flat** — otherwise fills get filtered until a position-start fill is found.
5. **Dependency:** "These tabs have 100% dependency on correct order fills" — Trades = fills + matching logic.

### Key Fields (from Text Export)
The **File >> Save Log As** / **Export** produces tab-separated text with:
- `ActivityType`: Orders | Fills | Positions
- `OpenClose`: Open | Close
- `InternalOrderID`, `ParentInternalOrderID`
- `FillPrice`, `FilledQuantity`, `BuySell`, `Symbol`, `Note`, `DateTime`, etc.

**Critical:** When you export from the **Trade Activity** tab, you get raw records. When you export from the **Trades** tab, you get the **pre-computed** trade list (Entry DateTime, Exit DateTime, PnL) — that matches SC exactly.

---

## 2. Binary Format (Reverse Engineered)

### 010 Editor Template
- **TradeActivityLog.bt** by George Tarantilis (March 2025) — [010 Editor repository](https://sweetscape.com/010editor/repository/templates/file_info.php?file=TradeActivityLog.bt&type=0)
- **ID bytes:** `01 00 00 00 08 00 00 00 02 00 00 00 00 00 00 00 00`
- Download and inspect to get full tag layout.

### Tags Our Parser Uses
| Tag | Hex | Purpose |
|-----|-----|---------|
| 102 | 0x66 | Timestamp (record start) |
| 104 | 0x68 | Message string |
| 107 | — | Order type (Market, Limit, Stop Limit) |
| 108 | 0x6C | Quantity |
| 100 | 0x64 | OrderID |
| 124 | 0x7C | ServiceOrderID |
| 130 | 0x82 | Note (strategy tag) |
| 103 | 0x67 | Symbol |

### Tags We Do NOT Parse (Likely in Binary)
- **OpenClose** (Open/Close) — needed for SC-exact pairing
- **ActivityType** (Fills vs Orders) — we infer from message
- **ParentInternalOrderID** — links Close to Open
- **InternalOrderID** — we use 100/124 which may be ServiceOrderID

**Action:** Obtain TradeActivityLog.bt or hex-compare binary vs text export to map OpenClose and InternalOrderID tags.

---

## 3. Why Binary FIFO ≠ SC Trades Tab

1. **SC uses order-based pairing** when available: Close fills reference ParentInternalOrderID → match to Open.
2. **We use pure FIFO** on raw fills — no order linkage.
3. **Result:** Different pairing → different trades. Example: SC 00:14 entry → 00:25 exit; our FIFO may pair 00:01 entry → 04:19 exit.

---

## 4. Paths to Match SC

### A. Use Trades Tab Export (Recommended)
- In SC: Trade Activity Log → **Trades** tab → File >> Save Log As
- Export has: Symbol, Trade Type, Entry DateTime, Exit DateTime, Entry Price, Exit Price, Quantity, PnL, etc.
- **One row per trade** — no pairing needed. Import directly.

### B. Use Activity Export with Open/Close
- Trade Activity tab → File >> Save Log As (ActivityType=Fills in display)
- Filter to Fills only. Use OpenClose + ParentInternalOrderID for pairing.
- **Caveat:** ParentInternalOrderID is often empty in exports → fallback to FIFO (current behavior).

### C. Cross-Source Matching Script (match_trades_1218.py)
- **Purpose:** Correlate Trade List, Activity List, Binary, and Chart annotations for a given day.
- **Usage:** `python match_trades_1218.py` (expects `1218 nq trade list.txt`, `1218 nq all activity list.txt` in project root).
- **Binary path:** `D:\SierraChart_Simulated_Feed\TradeActivityLogs\` (or from `app_settings.json` scanners for NQ).
- **Logic:** Parses Activity Fills, pairs Open+Close via ParentInternalOrderID (when populated) else FIFO. Parses binary via `_parse_file_nitro` (V_sim16 only). Compares to Trade List by entry/exit time+price+qty.
- **Result:** Reports match rate (e.g. 34/171 Trade List rows matched to Activity pairs). Binary FIFO pairs differ from SC order-based pairing; use Activity export as primary for SC-exact import.

### D. Reverse Engineer Binary for OpenClose
- Parse OpenClose and InternalOrderID from .data files.
- Requires: 010 Editor template analysis or byte-level comparison with known exports.
- Then: same pairing logic as Activity export.

### E. Match SC FIFO Settings
- Ensure `Edit >> Use Last In First Out` is **unchecked** (FIFO) if we use FIFO.
- Ensure **From Date** starts at flat — our session reset at 17:00 NY should align.

---

## 5. Immediate Next Steps

1. **Add Trades tab import** — parse 26-col TradesList format (Symbol, Trade Type, Entry DateTime, Exit DateTime, ...). No pairing; direct insert.
2. **Verify Activity export** — confirm we filter ActivityType=Fills and use correct columns (OpenClose, ParentInternalOrderID).
3. **Obtain TradeActivityLog.bt** — download from 010 Editor repo; document OpenClose/InternalOrderID tag IDs for binary parser enhancement.

---

*Created: Mar 1, 2026 — from SC docs, forums, and codebase analysis*
