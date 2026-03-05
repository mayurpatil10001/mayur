# 🛡️ Import Shield: Core Data Integrity Rules

This document outlines the definitive list of rules applied by the **Trading Analytics Platform** during binary trade ingestion from Sierra Chart TradeActivityLogs. These rules ensure 100% data integrity and eliminate ghost trades.

---

## Phase 1: Binary Parsing (`_parse_file_nitro`)

Each TradeActivityLog file is parsed independently. The parser extracts individual **fills** (buy/sell executions).

### Rule 1 — Fill Identification
*   **Target:** All binary TradeActivityLog files.
*   **Logic:** A record is identified as a fill when its message (Tag 104) contains `"(Filled)"` or `"Trade simulation fill"`.
*   **Required fields:** Symbol (Tag 103), Account (Tag 118), Price (extracted from message), Side (BUY/SELL from message), Quantity (Tag 108 or message, default=1).
*   **Exclusion:** Records containing `"Updated Internal Position"` or `"Updated Service Position"` are NOT fills.
*   **Order-type exclusion (TAL “Orders” not “Fills”):** The binary does not expose Activity Type. We approximate it: records with Tag 107 (Order Type) **"Stop"** (e.g. Stop Limit) are never emitted as fills. Records with Tag 107 **"Limit"** whose message does **not** contain `"Trading Evaluator"` are not emitted (they are TAL Order-status records, not Fills). Records with `"Trading Evaluator (Filled). Info: Trade simulation fill"` are still fills and are subject to Rule 2.
*   **Rationale:** Only actual execution confirmations are imported. Order submissions, cancellations, position updates, and Order-type records (03:05, 03:23, 03:43 in the TAL) are filtered out.

### Rule 2 — Adaptive Ghost Fill Detection (Pre-Filter vs Post-Pair)
*   **Target:** **ALL ACCOUNTS** (With Heuristic Bypass).
*   **Two modes:** (1) **Pre-FIFO:** Ghost fills dropped before pairing (`--no-defer`). (2) **Post-Pair (default):** Pair ALL fills first, then remove ghost trades (entry/exit contains ghost), then purge. Use `run_wipe_reimport_and_verify.py` without `--no-defer`.
*   **Heuristic (Adaptive Calibration):** Before filtering, the parser calculates the `Note-Rate` for the file (percentage of fills with Tag 0x82 populated).
    -   **No-Note Setup Bypass**: If **less than 25%** of fills have notes, the account is detected as an "Untagged Setup" (e.g., `TM_2`, `TM_10`). **Note-based filtering is disabled** for these files to prevent data loss.
    -   **Active Filtering**: If the note rate is ≥ 25% (e.g., `V_SIM16`, `IPS_TM_10`), the ghost filter is active.
*   **Ghost Criteria:** For active filtering files, a fill is a **ghost** if it has no Tag 0x82 Note and (when the message is considered) no strategy tag in the message (see below), and it is outside the 16:55-17:05 NY window.
*   **“Has strategy tag” (not a ghost):** A fill is treated as having a strategy tag if (a) Tag 0x82 Note is populated, or (b) the message contains `"Text: Tag"` or `"Tag: AT_"` (SC sometimes embeds the tag in the message). Exception: a fill whose message is plain `"Trade simulation fill"` (no `"Trading Evaluator"`) and Tag 107 is **Market** is treated as a real Fill (TAL Activity Type Fills) even without a note.
*   **Safety:** Any fill whose message contains `"Trading Evaluator"` but has no note and no `"Text: Tag"`/`"Tag: AT_"` in the message is forced to ghost and dropped (e.g. the 04:05 sync injection).
*   **Action (Pre-FIFO):** Ghost fills dropped before pairing. **Action (Post-Pair):** Ghost fills enter FIFO; after pairing, trades with ghost entry or exit are removed.
*   **Rationale:** Prevents phantom contracts from corrupting the mathematical position sequence, while safely adapting to user accounts where notes are not utilized. We do **not** block all “Trading Evaluator” messages: real fills can contain “Trading Evaluator (Filled)” and must be kept when they have a note or tag in the message.

### Rule 3 — EOD Flattening Exception
*   **Target:** All Accounts.
*   **Logic:** Fills occurring between **16:55 and 17:05 NY Time** are exempt from Rule 2 (Ghost Detection).
*   **Action:** Always accepted, even without a Tag 0x82 note.
*   **Rationale:** End-of-day flattening orders may not carry order notes. These must be captured to ensure the account position returns to zero for the next session.

### Rule 4 — 500ms-Precise Deduplication
*   **Target:** All Sync Operations.
*   **Logic:** Deduplication key is `(Timestamp rounded to 500ms, Price, Side, Quantity, MsgHash, InstancePath)`.
*   **Action:** Collapse duplicate records triggered by SC "Modify/Fill/Signal" loops.
*   **Rationale:** SC binary logs often emit multiple records for the same fill. 500ms is the proven bucket for catching these without merging distinct fast-fire executions.

---

## Phase 2: Fill Pairing — FIFO Reconstruction (`_pairs_to_trades`)

After parsing, fills are grouped and paired into complete trades (entry + exit).

### Rule 5 — Contract Isolation
*   **Target:** All Accounts.
*   **Logic:** Fills are grouped by **(account, specific contract symbol)** — e.g., `NQH26` and `CLJ26` are separate groups.
*   **Action:** Fills from different symbols or expirations **never cross-match**.
*   **Rationale:** Prevents Crude Oil fills from corrupting NQ position math.

### Rule 9 — Session-Boundary FIFO Reset (17:00 NY)
*   **Target:** All Accounts.
*   **Logic:** The FIFO matching queue is **hard-reset to empty** at every 17:00 NY session boundary.
*   **Action:** If a fill belongs to a new trading session date (as defined in Rule 9a), any residual open legs are flushed as "unpaired" and the session starts at zero.
*   **Rationale:** Solves the "Zombie Position" issue. Prevents ghost-induced position noise from leaking across days and matching with trades weeks later.

---

## Solved Issues (March 2026 Refresh)

| Issue | Root Cause | Fix Applied |
|---|---|---|
| **Zombie Positions** | Ghost fills created persistent "Open" legs that never closed. | **Rule 9 (17:00 Reset)** + **Rule 2 (Adaptive Ghost Filter)**. |
| **Multi-Day Hold Errors** | 17:00 NY close crosses weren't handled. | **Rule 9 (Session Boundary Reset)**. |
| **Crude/NQ Contamination** | Symbols matched across each other. | **Rule 5 (Contract Isolation)**. |
| **Double Ingestion** | Multiple SC Instances created duplicate records. | **Rule 4 (500ms Instance-Aware Dedup)**. |

---

*Maintained by Import Shield Service. Last Updated: Mar 4, 2026 (v4.5: Rule 9 Enforcement + 500ms Dedup Aligned)*
