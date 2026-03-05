Once validated, we can fully enforce raw fill reconstruction (via `binary_log_parser.py` or a dedicated Fills Paste Importer) to ensure our database reflects perfect accuracy.

## The Shield Platform: 5 Core Rules for Data Trust (Feb 26, 2026)

To achieve 100% data trust and eliminate corrupted stats, the system enforces the following 5 rules:

1.  **Rule #1: Binary Drift Guard (Diagnostic Warning)**
    - The engine monitors the real-time position during import. 
    - If a position drifts beyond the strategy limit (e.g., > 3 contracts), a **diagnostic warning** is logged. The fills are not blocked, as the primary fix is the removal of ghost fills (Rule #2).

2.  **Rule #2: Adaptive Ghost Filtering (The "Shield")**
    - The parser calculates the account's **Note-Rate** per session.
    - If Note-Rate > 25% (Standard Setup), fills without a **Note (Tag 0x82)** are blocked.
    - If Note-Rate < 25% (No-Note Setup), the filter bypasses to preserve all trades.
    - This intelligently eliminates ghost fills without impacting account configurations like `TM_2` or `TM_10`.

3.  **Rule #3: EOD Flattening Exception (Zero-State Integrity)**
    - Fills between **16:55 and 17:05 NY** are always accepted, even without a note.
    - This ensures mathematical totals always flatten to zero at the session close.

4.  **Rule #4: Statistical PnL Pruning (Outlier Shield)**
    - Any trade exceeding **5 standard deviations (5-sigma)** or a hard cap of **$50,000** is automatically purged.
    - This handles "Simulation Spikes" caused by bad data or gap handling.

5.  **Rule #5: Price Sanity Verification**
    - Executions with prices outside plausible ranges (e.g., NQ < 1000 or > 50000) are blocked.
    - This prevents database corruption from corrupt binary fragments.
