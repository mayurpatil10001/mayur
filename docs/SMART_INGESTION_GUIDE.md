# ⚡ Smart Ingestion & Selective Refresh System (April 2026 Update)

## Overview
The ingestion system has been upgraded from a global "all-or-nothing" approach to a **Targeted Account Refresh** system. This allows for rapid synchronization of specific account groups without the need for a full historical sweep.

## Key Features

### 1. Selective Account Refresh
Users can now check specific accounts in the **Systems Control Center** and trigger an import only for those accounts. This bypasses the need to scan all accounts in every SierraChart instance, drastically reducing sync time for active trading.

### 2. Smart Lookback Detection
The system no longer relies on a hardcoded "2000-day safety net" by default. 
- **Auto-Gap Calculation**: When a selective refresh is triggered, the engine calculates the gap (Days Ago) for the chosen accounts.
- **Dynamic Window**: It automatically scales the import window to `Max Gap + 2 Days`.
- **Performance**: This ensures that if you missed 2 days of trading, the system scans exactly 4 days of files, not 2,000.

### 3. Visual Feedback System
- **Processing Progress**: A new top-level progress bar tracks the "Ripping" phase (binary parsing).
- **Status Pills**: Real-time status indicators ("Calculating gap...", "Scanning 35 days...") provide immediate feedback on the engine's current operation.
- **Header Alignment**: Improved premium UI layout for better readability of performance stats vs system actions.

## Operational Tips

### Handling "System Import in Progress"
If the system is running a large historical scan (e.g., "Full History" checked), the **Database Status** (status dots) may occasionally turn red.
- **Cause**: High CPU/Disk I/O saturation and SQLite write-locks during bulk ingestion.
- **Effect**: The heartbeat requests may time out. This does **not** mean the database is corrupted; it just means the API is temporarily busy prioritizing the data integrity of the import.
- **Solution**: Wait for the "Ripping" phase to cross 90%, or use the **STOP** button to halt the scan and switch to a smaller lookback window.

### When to use Full History
Only use the **"FULL HISTORY"** checkbox when:
1. You are initializing a brand-new database.
2. You suspect historical trades from years ago have changed in the source files.
3. You are doing a once-a-month "deep sync" to ensure 100% database parity.

For daily operations, the **14-day default** or **Selective Refresh (Smart Lookback)** is recommended.

## ⚙️ Database Optimization (Performance Safeguards)

To prevent system hangs and "ages to load" issues during matrix recalculations, the following optimizations have been applied:

### 1. Ultimate Covering Indices
We have implemented covering indices on the `processed_trades` table that include `(symbol, hour_of_day, day_of_week, account_name, entry_time)`. This allows the Recommendation Matrix to compute complex rankings in < 5 seconds, even with millions of rows.

### 2. Server-Side TTL Caching
The API now employs a **60-second burst cache** for all recommendation queries. When you switch between modes (Classic -> Persistence -> Statistical), the system avoids re-querying the database if the underlying parameters haven't changed, making mode-switching virtually instant.

### 3. ISO Date Standardization
All date comparisons have been moved to direct ISO string matching (`entry_time >= ?`). This avoids expensive SQLite-side string parsing functions (`strftime`), further reducing CPU load during concurrent API requests.
