# Trade Import Logic and Validation

This document describes the mechanics of the trade import process from Sierra Chart into the Trading Optimization Platform and the methods used to validate data integrity.

## 1. Import Mechanism

The platform uses a "Comprehensive Processed Trade Importer" to ingest data from Sierra Chart's `SavedTradeActivity` logs.

### Key Components:
- **Script:** `comprehensive_processed_import.py`
- **Parser:** `trading_platform/services/processed_trade_parser.py`
- **Configuration:** `import_config.yaml` (defines directories and expected symbols)

### Logic Rules:
1. **Source Discovery:** Scans multiple Sierra Chart instance directories for `.txt` files containing trade activity.
2. **Account Detection:**
    - Attempts to read the `Account` column from the file.
    - If the column contains only a number, it extracts the full account name from the file name (e.g., `NQ_TS_4...txt` -> `TS_4`).
3. **Symbol Normalization:** Automatically maps instrument codes (e.g., `CLF25` -> `CL`, `NQH24` -> `NQ`).
4. **Timezone Handling & Display:** 
    - **Source:** Sierra Chart data is typically exported in **Local Time (ET)** or **SC Wall-Clock**.
    - **Storage:** The Platform Database stores all timestamps in **UTC** (standardizing across all log sources).
    - **Synchronization:** During import, the parser automatically detects the SC offset and converts all records to UTC.
    - **Display (The NY Sync):** For all UI views (Performance History, Trade List, Audit) and Analytics calculations (Hourly Breakdown), the platform automatically converts UTC back to **America/New_York**. This ensures the times shown on screen perfectly align with the user's local charts and the 17:00 NY session boundary.
5. **Trade ID Generation:** A unique hash is generated based on `Account + Symbol + Entry Time + Exit Time + Price + Quantity` to prevent duplicate imports.
6. **Flattening:** Multi-unit trades in Sierra Chart are often split into individual 1-unit records in the database, allowing for granular analysis of scale-ins and scale-outs.

## 2. Validation Process

To ensure the accuracy of the import (targeting >90% benchmark match), we use the following validation methodology.

### Binary-First Policy (Current)
- **Import source of truth:** Binary `TradeActivityLog_*.data` files.
- **Reference-only artifacts:** Trade List / All Activity exports are used only for benchmark and diagnostics.
- **Why:** One deterministic ingest path across all assets and days, with consistent session-boundary logic.

### Automated Validation Scripts:
- `tests/validate_cl_ts4_random.py`: Performs a random sampling of 10 trades and checks for their existence in the DB using DST-aware timezone offsets and price tolerances.
- `check_daily_counts.py`: Compares the distribution of trade counts per day between the source file and the database.
- `count_overall.py`: Provides a high-level comparison of total record counts.
- `tests/test_binary_benchmark_1218.py`: 12/18 V_SIM16 benchmark harness (binary parse/reconstruction + reference file wiring).

### Verification Results (CL TS_4):
- **Record Match:** 97.81%
- **Random Spot Check:** 90% Success
- **Observation:** Differences in P&L totals are expected due to commissions being applied per flattened record in the database.

## 3. How to Validate New Data

If new files are imported or a new symbol is added, follow these steps:

1. **Verify Counts:**
   ```powershell
   python count_overall.py
   ```
2. **Run Daily Distribution Check:**
   ```powershell
   python check_daily_counts.py
   ```
3. **Run 12/18 Binary Benchmark (reference-only):**
   ```powershell
   python -m pytest tests/test_binary_benchmark_1218.py -v --tb=short
   ```
4. **Perform Random Sampling:**
   Modify `tests/validate_cl_ts4_random.py` to target the specific symbol/account and run it.

## 4. Maintenance Notes
- **DST Transitions:** When validating across months, ensure the UTC offset logic in validation scripts matches the transition dates (March/November).
- **Symbol Extensions:** The importer currently supports `NQ`, `FDAX`, `ES`, and `CL`. New symbols must be added to `import_config.yaml`.
