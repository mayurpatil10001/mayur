# Binary Trade Match: Full Problem Summary and What We Tried

**Last updated:** March 2026  
**Benchmark:** 2025-12-18 NQ V_SIM16 (binary vs Sierra Chart Trade List)

This document summarizes the **problem** (getting binary-derived trades to match Sierra Chart’s Trade List) and **everything we tried** in recent work to improve or solve it.

---

## 1. The Problem

### 1.1 Goal

- **Source of truth:** Sierra Chart Trade Activity Log **binary** files (`.data` in `TradeActivityLogs`).
- **Benchmark:** Sierra Chart’s own **Trade List** (Trades tab) and **All Activity** (Fills) from the same account/day.
- **Target:** Import from binary and reconstruct **trades** (entry + exit pairs) so they match SC’s Trade List at a high rate (e.g. 90%+). We also need to avoid **wrong** trades: ghosts, >24h duration, closes after 17:00 EOD, and other anomalies documented in `\docs\`.

### 1.2 Why It’s Hard

1. **Binary has no ParentInternalOrderID**  
   SC pairs each **close** to a specific **open** using internal parent–child linkage. The binary export has **Open/Close** (tag 120) and **InternalOrderID** (tag 105) but **not** ParentInternalOrderID. Tag 139 on close records holds the close’s own ID, not the parent. So from binary alone we cannot reproduce SC’s exact pairing.

2. **Ghost fills**  
   In simulation, SC sometimes injects synthetic “fills” (e.g. Trading Evaluator at 04:05) to resync position after rollbacks. These appear in the binary as real Fill records but have **empty Note (tag 0x82)**. If we treat them as real, position and pairing go wrong (e.g. SC thinks +5 when we should stay +3, then “flips” trade order).

3. **Fills vs Orders in binary**  
   The binary does not expose “Activity Type” (Fills vs Orders). Records at 03:05, 03:23, 03:43 that are **Orders** in the TAL (canceled/rolled back) can look like fills in the binary. We must filter them (e.g. by Order Type tag 107, message text) so only true executions drive pairing.

4. **Session boundaries**  
   Trading day is 18:00–17:00 NY; we must reset FIFO at 17:00 and not pair across that boundary.

---

## 2. Data Sources and Constraints

| Source | Use | ParentInternalOrderID? |
|--------|-----|------------------------|
| Binary `.data` files | **Production import** (only source we can automate) | **No** |
| SC Trade List (Save As text) | Reference / benchmark only | Inferred from SC UI |
| SC All Activity (Save As text) | Reference / benchmark; has OpenClose + InternalOrderID | Yes (in text export) |

We do **not** rely on manual “Save Log As” for production; binary is the only ingest. Reference files are for validation and for the “reference-derived” pairing path when the user can provide them.

---

## 3. What We Tried (Chronological / by Area)

### 3.1 Binary Parsing (Tags and Fill Identification)

- **Direct tag parsing** instead of regex: added/used tags for timestamp (102), Note (130), message (104), Order Type (107), Quantity (108), OrderID/ServiceOrderID (100/124), Symbol (103), Side (109), FillPrice (113), FilledQty (114), Status (112), Open/Close (120), InternalOrderID (105), Position after fill (125), record code (101), ServiceOrderID (137), tag 139, TransDateTime (160).
- **Duplicate merging:** prefer latest snapshot per (instance, account, symbol, side, price, qty, time bucket) and merge metadata (e.g. `open_close`, `internal_order_id`, `position_after`).
- **Order-type filtering:** records with Tag 107 **Stop** (e.g. Stop Limit) are not emitted as fills; Tag 107 **Limit** without “Trading Evaluator” in message are dropped so 03:23/03:43 Order records don’t become fills.
- **Stable ordering:** added `_record_index` per fill for deterministic sort when times tie.

**Result:** Fill-level match to Activity list is ~99% once ghosts and order-type noise are filtered. Remaining gap is trade-level pairing, not fill extraction.

---

### 3.2 Ghost Detection and Removal

- **Definition:** Ghost = Fill record with **empty Tag 0x82 (Note)** and not in EOD window (16:55–17:05 NY). Exceptions: “Trade simulation fill” + Market with no “Trading Evaluator” = real; “Trading Evaluator” with “Text: Tag”/“Tag: AT_” in message = real.
- **Adaptive note-rate:** If &lt;25% of fills have a note, ghost filter is disabled (no-note accounts like TM_2).
- **Pre-FIFO drop (default):** Ghost fills are removed before pairing so they never enter the FIFO queues.
- **In-pairing skip (defer_ghost_removal):** When all fills are passed to the engine, we **skip** ghost fills in the loop: **ghost open** → do not add to buys/sells; **ghost close** → do not consume from queue. So we remove “only the leg,” keep the real entry, and the next real close pairs with it. Ledger can be synced from `position_after` (tag 125) when present.
- **Post-pair removal (legacy):** When defer_ghost_removal is on, trades whose entry or exit is ghost are removed after pairing; with in-pairing skip, this mainly catches rare ghost entries.

**Result:** Ghosts no longer corrupt position or pairing. The 04:05 +2 ghost is dropped or skipped so the 02:26 +3 is closed by the 04:18 -3, giving one correct long trade.

---

### 3.3 FIFO and Session Boundaries

- **Session date:** 17:00 NY boundary; FIFO queue reset when session date changes so we don’t pair across days.
- **Running position:** We maintain a `running_position` and sync it from binary `position_after` (tag 125) after each fill when available.
- **Contract isolation:** Fills grouped by (account, symbol); no cross-contract pairing.

**Result:** Session and contract rules are correct. Position ledger stays in sync with binary when tag 125 is present.

---

### 3.4 Improving Pairing (Binary-Only)

- **Position-update order:** `_scan_position_fill_order()` scans binary for “Updated Internal Position … Fill of InternalOrderID: X” (tag 104) and returns InternalOrderIDs in appearance order. We assign `_position_order` to each fill and sort by it, then `ts_val`, then file/record index so fill order matches SC’s execution order as closely as possible.
- **ServiceOrderID filter:** OPEN records whose tag 105 (InternalOrderID) is in 30M–39M range (ServiceOrderID) are skipped so we don’t double-count the same fill (e.g. 36782689 vs real 20091480). This improved strict match from ~14% to ~24%.
- **position_after (tag 125):** We use it to sync `running_position` after each fill. We **did not** use it to validate OPENs (e.g. skip OPEN when position_after disagrees) or to drive close quantity, because that dropped match rate sharply (e.g. to ~3–5%) and reduced trade count; the binary’s position_after can disagree with our FIFO when SC’s internal pairing differs.
- **LIFO:** Explored; did not improve match over FIFO for this benchmark.

**Result:** Binary-only strict trade match to SC Trade List is **~24%** (34/141 on 12/18 V_SIM16). Fill-level remains ~99%. No further binary-only heuristic tried so far has raised trade-level match meaningfully; the ceiling is set by missing ParentInternalOrderID.

---

### 3.5 Reference-Derived Pairing (When Reference Files Exist)

- **Idea:** Use SC Trade List + All Activity **text** exports to infer (entry_oid, exit_oid) per SC trade, then map binary fills by `internal_order_id` and build trades from those pairs.
- **Implementation:** `_exact_pairing_via_reference()` in `tests/test_binary_benchmark_1218.py`: match SC trade list entries/exits to Activity rows by (time, price, qty, side), build (entry_oid, exit_oid), then reconstruct trades from binary fills by InternalOrderID. Correct handling of Long/Short (entry_act_side / exit_act_side) and optional qty flexibility for partials.
- **Result:** **90%+** trade match in the benchmark test when reference files are used. Proves that with parent linkage (from text export) we can get SC-exact pairing; the limit is binary-only.

---

### 3.6 Reporting and Analysis

- **analyze_trade_mismatch.py:** Loads binary fills (with/without ghost), runs pairing, loads SC trade list, and produces a combined chronological table (binary + SC-only) with match status and reason (e.g. SAME_ENTRY_WRONG_EXIT, SAME_EXIT_WRONG_ENTRY, WRONG_ENTRY_AND_EXIT, pairing / ghost / close_after_17:00 / &gt;24h for SC-only). Writes `trade_mismatch_report.txt`.
- **Removed ghost trades:** When using fills that include ghosts, we diff trades from “with ghost” vs “no ghost” to list trades that would have been formed by ghost legs; with in-pairing skip, we no longer form those trades, so “removed” count can be 0 in that mode.

**Result:** Clear picture of who matches, who doesn’t, and why (pairing vs ghost vs session vs duration).

---

## 4. Current State (Metrics)

| Metric | Value |
|--------|--------|
| **Binary-derived trades (12/18 V_SIM16)** | 141 |
| **SC trade list trades** | 171 |
| **Strict matches (binary vs SC)** | 34 (**24.1%** of binary) |
| **Fill-level match to Activity** | ~99% |
| **Trade-level match with reference-derived pairing** | **90%+** (when Trade List + Activity exports used) |

Unmatched binary trades are mostly: **WRONG_ENTRY_AND_EXIT** (48), **SAME_EXIT_WRONG_ENTRY** (27), **SAME_ENTRY_WRONG_EXIT** (24), **NO_SC_CLOSE_MATCH** (8). Root cause: FIFO vs SC’s parent-based pairing when multiple opens/closes exist in the same timeframe.

---

## 5. What Works vs What Doesn’t

**Works:**

- Parsing binary .data (tags, dedup, fill vs order-type filtering).
- Ghost detection (empty Note, EOD exception, adaptive note-rate) and removal (pre-FIFO drop or in-pairing skip of ghost open/close only).
- Session boundary (17:00 NY) and contract isolation.
- FIFO + Open/Close + position-update order + ServiceOrderID filter + position_after sync → **~24%** binary-only trade match, **~99%** fill match.
- Reference-derived pairing → **90%+** trade match when reference files are available.
- Reporting and mismatch analysis (reasons, chronological table, removed ghosts).

**Does not work (binary-only):**

- Reaching 90%+ trade match without ParentInternalOrderID (or equivalent) or reference data. Every heuristic we tried (position order, position_after sync, ServiceOrderID filter, ghost leg skip) improved or protected correctness but could not close the pairing gap; the gap is structural.

---

## 6. Options Going Forward

| Option | Description | Trade match |
|--------|-------------|-------------|
| **A. Binary-only (current)** | No reference files; FIFO + all current rules. | ~24% |
| **B. Reference-derived** | When user can export Trade List + Activity, use them to infer (entry_oid, exit_oid) and build trades from binary fills. | 90%+ |
| **C. SC change** | Ask Sierra Chart to add ParentInternalOrderID (or equivalent) to binary/export. | Would allow 90%+ binary-only; SC has not committed to this. |
| **D. Manual export** | Use SC “Save Log As” (Fills/Trades) as import source instead of binary. | Can match SC exactly but not automated from .data. |

See also: `docs/ghost_trade_identification.md` (SC’s position, Support Board threads, workarounds), `docs/IMPORT_SHIELD_CORE_RULES.md` (all rules), `docs/trade_match_analysis_and_solution.md` (tables and solution options).

---

## 7. Key Files

| File | Role |
|------|------|
| `trading_platform/services/binary_log_parser.py` | Parse .data, ghost detection, FIFO pairing, position order, ghost open/close skip. |
| `tests/test_binary_benchmark_1218.py` | Benchmark loaders, reference-derived pairing, strict match %. |
| `analyze_trade_mismatch.py` | Mismatch report (binary vs SC, reasons, chronological table). |
| `trade_mismatch_report.txt` | Output of the above (full table and summary). |
| `docs/ghost_trade_identification.md` | Ghost definition, chart scenario, SC docs, “what SC says.” |
| `docs/IMPORT_SHIELD_CORE_RULES.md` | All import rules (parsing, pairing, purge). |
| `docs/trade_match_analysis_and_solution.md` | Match tables, mismatch reasons, options A/B/C. |

---

*Summary covers work through March 2026: parsing, ghost handling, FIFO/session/position order, ServiceOrderID filter, position_after sync, reference-derived pairing, and reporting.*
