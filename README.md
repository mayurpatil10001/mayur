# Sierra Chart Trade Optimization & Analytics Platform (`SC_results_WF`)

**`SC_results_WF`** is a production-grade, multi-account quantitative trading analytics platform designed for Sierra Chart (SC). It parses raw SC binary trade activity logs (`.data` files in Sierra Chart's proprietary Tag-Length-Value binary format), eliminates platform-level execution corruption using the bespoke **Ghost Fill Resynchronization Engine (GFRE v2)**, stores verified strategy-attributed trades in a SQLite database, evaluates time-of-day statistical edge using Benjamini-Hochberg FDR correction, and exposes interactive analytics via a FastAPI backend and React/TypeScript dashboard.

> **Technical Reference Notice**: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) contains the complete low-level technical specification (binary TLV tag mapping, SQLite schema, GFRE algorithm steps, investigation log). This `README.md` serves as the primary system entry point and broad architecture document.

---

## Table of Contents

1. [Project Mission](#1-project-mission)
2. [Current System Status — August 2026](#2-current-system-status--august-2026)
3. [The Ghost Fill Problem](#3-the-ghost-fill-problem)
4. [Ghost Fill Resynchronization Engine v2 (GFRE)](#4-ghost-fill-resynchronization-engine-v2-gfre)
5. [Full Dataset Cleaning Pipeline](#5-full-dataset-cleaning-pipeline)
6. [NQ Empirical Validation Case Study](#6-nq-empirical-validation-case-study)
7. [Architecture Overview](#7-architecture-overview)
8. [Data Sources and Binary Format](#8-data-sources-and-binary-format)
9. [Database Schema](#9-database-schema)
10. [Backend API Reference](#10-backend-api-reference)
11. [Frontend Dashboard](#11-frontend-dashboard)
12. [Statistical Edge Analysis](#12-statistical-edge-analysis)
13. [Account and Asset Mapping](#13-account-and-asset-mapping)
14. [Key Files and Scripts](#14-key-files-and-scripts)
15. [Output Reports](#15-output-reports)
16. [How to Run](#16-how-to-run)
17. [Technology Stack](#17-technology-stack)
18. [Security](#18-security)
19. [Investigation Timeline](#19-investigation-timeline)
20. [Known Limitations](#20-known-limitations)
21. [Open Questions and Next Steps](#21-open-questions-and-next-steps)

---

## 1. Project Mission

The `SC_results_WF` platform was built to answer a fundamental quantitative question:
**Do automated C++ trading strategies running inside Sierra Chart possess a statistically defensible trading edge?**

To evaluate this accurately, the platform must first resolve a critical data-layer challenge:
**Is the execution log emitted by Sierra Chart truthful?**

Sierra Chart records every fill, order status update, position change, and system message across dozens of trading accounts into binary `.data` files. These files are the ground truth of strategy behavior. However, during development, we discovered that Sierra Chart's internal Trade Evaluator engine silently injects untagged fill records — termed **ghost fills** — into the binary log stream. These ghost fills corrupt position tracking and invalidate downstream metrics.

The Ghost Fill Resynchronization Engine (GFRE) was built to solve this data integrity challenge. Only after the execution stream is sanitized can statistical edge analysis (BH-FDR, Out-of-Sample testing, permutation tests) be meaningfully conducted.

### Core Objectives:
- **Parse Binary TLV Logs**: Decode Sierra Chart's proprietary binary structure without relying on exported text logs.
- **Sanitize Fills via GFRE v2**: Detect and purge un-attributed Trade Evaluator fills while preserving legitimate strategy trades.
- **Resynchronize FIFO Sequences**: Match entries and exits using Sierra Chart's exact execution sequence index (`_position_order`).
- **Compute Reliable Metrics**: Calculate true PnL, Win Rate, Drawdown, and Sortino Ratios across accounts and symbols.
- **Evaluate Statistical Edge**: Apply Benjamini-Hochberg False Discovery Rate (FDR) control to identify time-of-day edge slots.
- **Out-of-Sample Audit**: Test identified time-of-day slots strictly out-of-sample on unseen test data.


## 2. Current System Status — August 2026

### GFRE v2 — Deployed and Validated

The Ghost Fill Resynchronization Engine v2 is fully operational in
`trading_platform/services/ghost_fill_engine.py`.

**v2 fixes over v1 (shipped July 2026):**
- `classify_fill()` correctly exempts `CLOSE` fills from the Evaluator-rule — previously, Trade Evaluator CLOSE records were misclassified as ghosts, causing legitimate exit fills to be dropped.
- `_duration_min()` absolute-value bug fixed — negative durations no longer propagate to RoundTrip records.
- `verify_sequence()` now checks for inverted trades (`exit_time < entry_time`).

**Validated on:**  
`IPS_TM_7` | NQ | 2026-06-10 to 2026-07-23 | 22 active trading days  
→ 2 previously unexplained pathological dates (2026-06-23, 2026-07-02) fully resolved.  
→ 2026-07-09 root-caused via fill-by-fill FIFO trace: 2 genuine ghost OPEN fills confirmed; $7,550 PnL swing is a cascade amplification effect, **not a classifier error**.

### Full Dataset Cleaning — IN PROGRESS

**61,706 source files** | **177 accounts** | **2024-01-21 to 2026-07-17**  
Ghost rate confirmed: **~10.2%** of fills are ghosts on fill-bearing accounts.  
Status: Running as `python ghost_fill_cleaner.py` | ETA ~1.5 hours from last launch.

### Production Database
- `processed_trades` table: **126,991** clean, verified round-trip strategy trades.
- FastAPI backend: live at `http://localhost:8000`.
- React/TypeScript dashboard: live at `http://localhost:3000`.


## 3. The Ghost Fill Problem

### Discovery
The ghost fill issue was uncovered during a diagnostic audit triggered by anomalous trade metrics:
1. Automated strategies designed for 20-40 trades per day were generating hundreds of executions.
2. Daily PnL inverted on days with strong directional market moves aligned with strategy bias.
3. `Updated Internal Position Quantity` binary log messages showed sudden position drops to 0 without corresponding strategy exit signals.

### Mechanics of a Ghost Fill
A **Ghost Fill** is an execution entry logged in Sierra Chart binary `.data` files that lacks a C++ strategy attribution tag (Tag `0x82` Order Note).

- **Real Strategy Fill**: Contains Tag `0x82` with prefix `AutoTrader_` (e.g., `AutoTrader_TM_7_v3`) or strategy tag in Tag 104 message text (`Text: Tag: AutoTrader_...`).
- **Ghost Fill**: Contains Tag 104 message `Trading Evaluator (Filled). Info: Trade simulation fill...` but **NO Tag `0x82`** and no strategy tag.

### Root Cause
When a C++ DLL study submits a limit or stop order, it attaches an Order Note. Sierra Chart records this note as Tag `0x82`. However, when Sierra Chart's internal **Trade Evaluator** matches that pending order against market data, it generates a new fill record *without* copying over the `0x82` note tag.

### The Direction Flip Cascade
A single ghost fill silently alters the parser's internal position tracker, causing subsequent signals to execute in reverse:

```
REAL POSITION:        Short 3 contracts (pos = -3)
GHOST FILL FIRES:     BUY 3 @ 24534.0 (pos: -3 -> 0) [Strategy unaware]
STRATEGY STATE:       Thinks position is still Short -3
STRATEGY SIGNAL:      Fires "BUY to exit Short"
SC EXECUTION:         Executes BUY 3 @ 24465.0 (pos: 0 -> +3) [Now unintended LONG]
STRATEGY SIGNAL:      Fires next "SELL to enter Short"
SC EXECUTION:         Executes SELL 3 @ 24438.0 (pos: +3 -> 0) [Closes unintended Long]

RESULT: Injected phantom cycle (1 ghost + 2 orphaned fills), injecting fake PnL/losses.
```


## 4. Ghost Fill Resynchronization Engine v2 (GFRE)

The GFRE sanitizes fill streams through a 5-stage pipeline:

```
[Raw Binary Fills]
       │
       ▼
Stage 1: Tag-Validation Filter (classify_fill)         ← v2: CLOSE exemption fixed
       │  • Rule 1: 1-lot exemption (qty == 1 -> keep)
       │  • Rule 2: EOD exemption (16:55-17:05 NY -> keep)
       │  • Rule 3: Evaluator + OPEN + No Tag -> DROP (GHOST)
       │  • Rule 4: CLOSE fills -> KEEP (regardless of note)  ← NEW in v2
       ▼
Stage 2: Adaptive Bypass Detection (_compute_note_rate)
       │  • If <25% of fills have notes (e.g. TM_10), bypass filter
       ▼
Stage 3: Per-Batch Deduplication (_dedup_fills)
       │  • 250ms bucket deduplication, keeping richer note-bearing records
       ▼
Stage 4: FIFO Position Resynchronizer (pair_fills_to_trades)
       │  • FIFO position tracking using SC execution order (_position_order)
       │  • Emits clean RoundTrip trades (ENTRY, EXIT, SCALE-OUT, FLIP)
       ▼
Stage 5: Sequence Integrity Verifier (verify_sequence)         ← v2: inverted trade check
       │  • verify_sequence(raw_fills, clean_fills, trades, unpaired)
       │  • Returns (bool, List[str], int): (ok, messages, flip_count)
       │  • Checks: net position balance, direction flips, inverted trades
       ▼
[Sanitized RoundTrip Trades]
```

### Detailed Stage Breakdown:

#### Stage 1: Tag-Validation Filter (`classify_fill`) — v2
Evaluates every candidate fill against 4 deterministic rules:
- **Rule 1 (1-Lot Exemption)**: 1-contract fills are preserved unconditionally.
- **Rule 2 (EOD Exemption)**: Fills between 16:55 and 17:05 NY wall-clock time are preserved.
- **Rule 3 (Evaluator OPEN Rule)**: `OPEN` fills containing `Trading Evaluator` in message text MUST contain a strategy tag (`AutoTrader_`, `AT_`, `Text: Tag:`). Missing tag → flagged as Ghost.
- **Rule 4 (CLOSE Exemption — v2 fix)**: All `CLOSE` fills are preserved unconditionally. Previously, Evaluator CLOSE records were being dropped, corrupting exit pairing.

#### Stage 2: Adaptive Bypass Detection (`_compute_note_rate`)
Calculates the fraction of fills in a file containing Tag `0x82` notes. If note coverage is under 25% across >5 fills (e.g. `TM_10`), ghost filtering is automatically bypassed for that file.

#### Stage 3: Per-Batch Deduplication (`_dedup_fills`)
Groups fills into 250ms windows. Keeps the note-bearing version if duplicates exist.

#### Stage 4: FIFO Position Resynchronizer (`pair_fills_to_trades`)
Maintains an internal signed position counter and open-leg queue. Fills are sorted by Sierra Chart's execution order index (`_position_order`), then timestamp. Matches entries with exits to produce completed `RoundTrip` objects.

#### Stage 5: Sequence Integrity Verifier (`verify_sequence`) — v2
```python
ok, messages, flip_count = verify_sequence(raw_fills, clean_fills, trades, unpaired)
```
Checks:
1. Net position delta at session end equals 0 (or unpaired qty).
2. Direction flips in the clean fill stream equal 0.
3. **NEW v2**: Inverted trades (`exit_time < entry_time`) — flags FIFO pairing errors.


## 5. Full Dataset Cleaning Pipeline

### Overview

The `ghost_fill_cleaner.py` script implements a **batched, resumable, checkpoint-safe** cleaning pipeline over the full ~100GB dataset. It runs the complete GFRE v2 pipeline on every file, writes clean trades to a staging database, and saves progress every 50 files so any interruption can be resumed with a single command.

### Confirmed Numbers (from benchmark + live run)

| Metric | Value |
|--------|-------|
| Total source files | 61,706 |
| Accounts covered | 177 |
| Date range | 2024-01-21 to 2026-07-17 |
| Ghost fill rate (fill-bearing accounts) | ~10.2% |
| Throughput | ~8–16 files/sec (11 threads) |
| Estimated total runtime | 1.5–2.5 hours |
| PnL flag threshold | >15% delta triggers review flag |

### Commands

```bash
# Start OR resume from where you left off (same command always)
python ghost_fill_cleaner.py

# Check status anytime (works while running or paused)
python ghost_fill_cleaner.py --status

# Preview plan without processing
python ghost_fill_cleaner.py --dry-run

# Start completely over (wipes checkpoint + output DB)
python ghost_fill_cleaner.py --reset

# Use fewer CPU cores (e.g. to keep machine responsive)
python ghost_fill_cleaner.py --workers 6
```

### Output Files

| File | Contents |
|------|----------|
| `trading_platform_clean_v2.db` | SQLite staging DB — clean trades + per-file audit |
| `.gfre_checkpoint.json` | Resumable checkpoint (saved every 50 files) |

**`trading_platform_clean_v2.db` tables:**

- **`clean_trades`**: Every clean RoundTrip trade after ghost removal. Columns: `account`, `symbol`, `base_symbol`, `trade_date`, `entry_time`, `exit_time`, `direction`, `quantity`, `entry_price`, `exit_price`, `pnl_dollars`, `pnl_points`, `duration_min`, `entry_note`, `exit_note`, `gfre_version`, `source_file`.
- **`file_audit`**: One row per source file. Columns: `total_raw_fills`, `ghost_fills`, `bypass_mode`, `note_coverage`, `dirty_trades`, `clean_trades`, `dirty_net`, `clean_net`, `pnl_delta`, `pnl_delta_pct`, `integrity_ok`, `integrity_notes`, `flagged`, `flag_reason`, `asset_list`.

> **Production DB (`trading_platform.db`) is never touched.** All cleaning output goes only to `trading_platform_clean_v2.db` until explicit promotion sign-off.

### Querying Results

```python
import sqlite3
con = sqlite3.connect(r'C:\SC_results_WF\trading_platform_clean_v2.db')

# Clean trades for one account
rows = con.execute("""
    SELECT account, symbol, trade_date, direction, pnl_dollars
    FROM clean_trades WHERE account = 'IPS_TM_7'
    ORDER BY trade_date, entry_time
""").fetchall()

# Net PnL by account
rows = con.execute("""
    SELECT account, COUNT(*) trades, SUM(pnl_dollars) net_pnl
    FROM clean_trades GROUP BY account ORDER BY net_pnl DESC
""").fetchall()

# Files needing manual review
rows = con.execute("""
    SELECT source_file, pnl_delta, flag_reason
    FROM file_audit WHERE flagged=1
    ORDER BY ABS(pnl_delta) DESC
""").fetchall()
```


## 6. NQ Empirical Validation Case Study

### Overview (June 10 – July 23, 2026 | 22 Active NQ Days)
A side-by-side comparison of **Dirty** (unfiltered data) vs. **GFRE v2 Clean** (sanitized data) on NQ strategy executions (`IPS_TM_7.data`):

| Metric | Dirty Baseline | GFRE v2 Clean | Difference / Impact |
| :--- | ---: | ---: | :--- |
| **Total Realized PnL ($)** | +$18,800.00 | **-$3,925.00** | ❌ -$22,725.00 overstatement removed |
| **Executed Trades** | 898 | **849** | -49 phantom trades purged |
| **Win Rate (%)** | 67.4% | **58.9%** | -8.5pp false win rate bias removed |
| **Max Drawdown ($)** | $38,970.00 | **$65,885.00** | True drawdown risk 69% higher |
| **Ghost Fills Dropped** | 0 | **33** | 100% ghost fills purged |
| **Direction Flips** | ~33 cascades | **0** | All position corruption eliminated |
| **Integrity Pass Rate** | 68% | **100% (22/22 days)** | All sessions close flat |

### Key Dates Traced:
- **June 23, 2026**: Ghost fills created fake -$1,950 loss. GFRE revealed actual PnL **+$31,150** (+$33.1k swing). ✅ Fully resolved.
- **July 02, 2026**: 1 ghost fill reshuffled pairing, revealing -$40,795 vs -$4,960 dirty (-$35.8k correction). ✅ Fully resolved.
- **July 09, 2026**: 2 confirmed ghost OPEN fills (IDX=28, 29). $7,550 PnL swing is FIFO cascade amplification — classifier is correct, source data has CLOSE fills on a flat position. ⚠️ Open — data integrity issue, not a classifier bug.
- **Clean Days (7 days)**: June 24, 28, 30, July 3, 6, 12, 16 — Dirty and Clean results **100% identical** (zero false positives confirmed).


## 7. Architecture Overview

```
                      +---------------------------------------+
                      |       Sierra Chart Platform           |
                      |  C++ DLL AutoTrader Strategy Engine   |
                      +-------------------+-------------------+
                                          |
                                          | Binary log output (.data)
                                          v
                      +---------------------------------------+
                      |    dataset/*.data Binary TLV Files    |
                      |  TradeActivityLog_YYYY-MM-DD_UTC.     |
                      |  <AccountName>.data                   |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |   binary_log_parser._parse_file_nitro |
                      |   - Pre-scans FIFO position orders    |
                      |   - Decodes TLV tags (0x66, 0x82 etc) |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |  Ghost Fill Resynchronization Engine  |
                      |  ghost_fill_engine.py  (GFRE v2)      |
                      |  - 5-Stage Filtering & Verification   |
                      |  - CLOSE fill exemption (v2 fix)      |
                      |  - Inverted trade detection (v2 fix)  |
                      +-------------------+-------------------+
                                          |
                          ┌───────────────┴───────────────┐
                          ▼                               ▼
          +-------------------------------+  +-------------------------------+
          | trading_platform.db           |  | trading_platform_clean_v2.db  |
          | (production — read only)      |  | (staging — batch clean run)   |
          | Table: processed_trades       |  | Tables: clean_trades,         |
          | 126,991 rows                  |  |         file_audit            |
          +-------------------------------+  +-------------------------------+
                          |
                          v
                      +---------------------------------------+
                      |  FastAPI Backend (localhost:8000)     |
                      |  - REST endpoints for analytics       |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |  React Dashboard (localhost:3000)     |
                      |  - Interactive PnL & Leaderboards     |
                      +---------------------------------------+
```


## 8. Data Sources and Binary Format

### Binary Log Structure
Files are stored in `dataset/TradeActivityLog_YYYY-MM-DD_UTC.<AccountName>.data`.

Each record follows the TLV structure:
- `[4 bytes: Tag uint32 LE]`
- `[4 bytes: Length uint32 LE]`
- `[Length bytes: Value payload]`

### Key TLV Tags

| Tag (Dec) | Tag (Hex) | Type | Name | Purpose |
| ---: | :--- | :--- | :--- | :--- |
| 102 | 0x66 | float64 LE | Timestamp | SC OLE date (days since 1899-12-30) |
| 103 | 0x67 | String | Symbol | Instrument symbol (`FDAXM26`, `NQU26`) |
| 104 | 0x68 | String | Message Text | Contains execution message details |
| 107 | 0x6B | String | Order Type | `Market`, `Limit`, `Stop Limit` |
| 109 | 0x6D | Byte | Side | 1 = BUY, 2 = SELL |
| 113 | 0x71 | float64 LE | Fill Price | Execution price |
| 114 | 0x72 | float64 LE | Qty | Executed contract quantity |
| 120 | 0x78 | Byte | Open/Close | 1 = OPEN (entry), 2 = CLOSE (exit) |
| 125 | 0x7D | float64 LE | Position After | Signed position quantity after fill |
| **130** | **0x82** | **String** | **Order Note** | **Ghost Detection Key (Real: `AutoTrader_`, Ghost: Empty)** |


## 9. Database Schema

### Production DB: `trading_platform.db`
```sql
CREATE TABLE processed_trades (
    trade_id           TEXT PRIMARY KEY,
    account_name       TEXT,
    symbol             TEXT,
    entry_time         TEXT,          -- ISO 8601 UTC string
    exit_time          TEXT,          -- ISO 8601 UTC string
    entry_price        REAL,
    exit_price         REAL,
    quantity           INTEGER,
    side               TEXT,          -- 'BUY' or 'SELL'
    profit_loss        REAL,          -- Realized PnL ($ / EUR)
    commission         REAL,
    duration_minutes   INTEGER,
    hour_of_day        INTEGER,       -- 0-23 UTC
    day_of_week        INTEGER,       -- 0=Mon, 6=Sun
    trip_id            TEXT,
    minute_of_hour_ny  INTEGER        -- NY minute key for slot analysis
);
```

### Staging DB: `trading_platform_clean_v2.db`
```sql
CREATE TABLE clean_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account         TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    base_symbol     TEXT,             -- resolved root (NQ, ES, CL, etc.)
    trade_date      TEXT,
    entry_time      TEXT,
    exit_time       TEXT,
    direction       TEXT,
    quantity        INTEGER,
    entry_price     REAL,
    exit_price      REAL,
    pnl_dollars     REAL,
    pnl_points      REAL,
    duration_min    REAL,
    entry_note      TEXT,
    exit_note       TEXT,
    gfre_version    TEXT DEFAULT 'v2',
    source_file     TEXT,
    imported_at     TEXT
);

CREATE TABLE file_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file     TEXT UNIQUE NOT NULL,
    account         TEXT,
    trade_date      TEXT,
    processed_at    TEXT,
    total_raw_fills INTEGER,
    ghost_fills     INTEGER,
    bypass_mode     INTEGER,
    note_coverage   REAL,
    dirty_trades    INTEGER,
    clean_trades    INTEGER,
    dirty_net       REAL,
    clean_net       REAL,
    pnl_delta       REAL,
    pnl_delta_pct   REAL,
    integrity_ok    INTEGER,
    integrity_notes TEXT,
    flagged         INTEGER,          -- 1 if |pnl_delta_pct| > 15%
    flag_reason     TEXT,
    asset_list      TEXT
);
```


## 10. Backend API Reference

FastAPI runs on `http://localhost:8000`. Interactive documentation at `http://localhost:8000/docs`.

### Key Endpoints:
- `GET /analytics/performance`: Aggregate PnL, Win Rate, Profit Factor by account/symbol.
- `GET /analytics/time-bins`: 30-minute time slot performance breakdown.
- `GET /analytics/sortino-leaderboard`: Ranked accounts by annualized Sortino ratio.
- `GET /analytics/drawdown`: Equity drawdown series data.
- `GET /trades`: Filterable trade history list.
- `POST /import/trigger`: Run binary log scanner and GFRE import.


## 11. Frontend Dashboard

React 18 + TypeScript SPA running on `http://localhost:3000`.

- **SimpleDashboard.tsx**: Key metrics cards (Win Rate, Profit Factor, Sortino) & cumulative PnL chart.
- **SortinoLeaderboard.tsx**: Account leaderboard sorted by risk-adjusted return.
- **TimeSlotHeatmap.tsx**: Interactive 30-minute time-of-day edge heatmap.
- **TradeHistory.tsx**: Searchable, filterable trade execution table.


## 12. Statistical Edge Analysis

### Out-of-Sample Audit (`2025-01-01 to 2025-10-31`)
Time-of-day slots selected during in-sample training (`2023-09-04 to 2024-12-31`) were frozen and evaluated strictly out-of-sample:

| Metric | Baseline (Raw) | BH-FDR Pipeline (Frozen Slots) |
| :--- | ---: | ---: |
| **Total Realized PnL** | -$1,264,608.50 | **-$117,987.50** |
| **Executed Trades** | 38,415 | **383** |
| **Win Rate** | 51.83% | **57.18%** |
| **Profit Factor** | 0.98 | **0.79** |
| **Annualized Sharpe** | -0.07 | **-0.88** |

> **Verdict**: The time-of-day slot edge discovered in-sample does **not** persist out-of-sample, indicating regime non-stationarity.


## 13. Account and Asset Mapping

| Account Suffix | Primary Asset | Multiplier |
| :--- | :--- | :--- |
| `.TM_7.data` | FDAX (DAX Futures) | EUR 25.00 / pt |
| `.IPS_TM_7.data` | NQ (Nasdaq-100), CL (Crude Oil) | USD 20.00 / pt (NQ), USD 1,000 / $1 (CL) |
| `.ES-TM_7.data` | ES (S&P 500 E-mini) | USD 50.00 / pt |
| `TM_1` – `TM_10` | Multi-asset | Varies |
| `IPS_TM_1` – `IPS_TM_10` | Multi-asset (IPS variant) | Varies |
| `PB_1` – `PB_3` | Multi-asset | Varies |
| `3Q_sim*`, `A_sim*`, `B_sim*` | Simulation accounts | Stub/sparse files |

**Excluded from cleaning** (anomalous instruments or non-standard scaling):
`T-S_production`, `Tsufim-Prod`, `Unset`, `Depth`, `A_production_14_16_19`, `A_production_16`, `A_production_19`


## 14. Key Files and Scripts

| File | Purpose |
|------|---------|
| [`ghost_fill_cleaner.py`](ghost_fill_cleaner.py) | **Main entry point** — resumable batch ghost-fill cleaner for 61k+ files |
| [`trading_platform/services/ghost_fill_engine.py`](trading_platform/services/ghost_fill_engine.py) | GFRE v2 — `classify_fill`, `pair_fills_to_trades`, `verify_sequence` |
| [`trading_platform/services/binary_log_parser.py`](trading_platform/services/binary_log_parser.py) | TLV parser — `_parse_file_nitro` |
| [`scripts/verify_ghost_clean.py`](scripts/verify_ghost_clean.py) | Verification script — confirms ghost removal on known-fill accounts |
| [`scripts/_fast_verify.py`](scripts/_fast_verify.py) | Quick 5-file verification + thread vs direct parse diagnostic |
| [`scripts/_check_progress.py`](scripts/_check_progress.py) | Reads checkpoint JSON, prints per-account file counts |
| [`scripts/step4a_trace_jul09.py`](scripts/step4a_trace_jul09.py) | Fill-by-fill FIFO trace for 2026-07-09 pathological case |
| [`scripts/step1_benchmark.py`](scripts/step1_benchmark.py) | Throughput benchmark — measured 4.5–16 files/sec |
| `trading_platform/services/trade_import_service.py` | DB import service for production table |
| `PROJECT_OVERVIEW.md` | Complete low-level technical specification |


## 15. Output Reports

- `trading_platform_clean_v2.db`: **Primary output** — all clean trades post ghost removal (staging).
- `.gfre_checkpoint.json`: Resume checkpoint (do not delete until run is 100% complete).
- `docs/nq_gfre_comparison_jun10_jul23.csv`: Day-by-day NQ dirty vs clean comparison.
- `docs/tm7_nq_full_signal_fill_sync.csv`: 31-day signal match rate report.
- `docs/OUT_OF_SAMPLE_RESULTS.md`: Out-of-sample statistical audit.
- `docs/PERMUTATION_TEST_RESULTS.md`: 1,000-iteration permutation test results.


## 16. How to Run

### Ghost Fill Cleaning (primary task — use this to clean 100GB dataset):
```bash
# From project root: C:\SC_results_WF\

# Start or resume cleaning
python ghost_fill_cleaner.py

# Check progress anytime (safe to run while cleaning is active)
python ghost_fill_cleaner.py --status

# Stop: press Ctrl+C in the running terminal
# Resume: run the same command again
python ghost_fill_cleaner.py
```

### Full Platform Stack:
```cmd
# Windows Quick Launcher:
START.bat

# Backend only:
scripts\start_backend_only.bat
```

### Manual Setup:
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run backend
python main.py

# Run frontend
cd frontend
npm install
npm start
```


## 17. Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, SQLite3, asyncio, concurrent.futures (ThreadPoolExecutor)
- **Analytics**: Pandas, NumPy, SciPy, Statsmodels, scikit-learn
- **Frontend**: React 18, TypeScript, Redux Toolkit, Plotly.js
- **Build/CI**: Docker Compose, GitHub Actions
- **Cleaning Pipeline**: `ghost_fill_cleaner.py` — batched, resumable, checkpoint-safe, 11 threads

---

## 18. Security

- All API keys and DB credentials managed via `.env` (excluded via `.gitignore`).
- `dataset/` binary files and `*.db` databases are excluded from git repository.
- JWT authentication implemented with configurable expiration.

---

## 19. Investigation Timeline

1. **Anomaly Identification**: Trade frequency spike & PnL inversion detected.
2. **Root Cause Isolation**: Sierra Chart Trade Evaluator identified as source of un-tagged OPEN fills (Tag 0x82 absence).
3. **GFRE v1 Engine Built**: 5-stage resynchronization engine implemented and deployed.
4. **Database Sanitization**: ~606,856 phantom trade records purged from production DB.
5. **GFRE v2 Fix**: CLOSE fill exemption bug fixed; `_duration_min()` abs() fixed; inverted trade check added (July 2026).
6. **Fill-by-Fill Trace**: 2026-07-09 pathological case root-caused via FIFO trace — 2 confirmed ghost OPEN fills, cascade amplification identified (not a classifier error).
7. **Full Dataset Cleaning Pipeline Built**: `ghost_fill_cleaner.py` — resumable, checkpointed, 61,706 files (August 2026).
8. **Ghost Rate Confirmed**: 10.2% ghost fill rate on fill-bearing accounts (measured live, August 2026).

---

## 20. Known Limitations

- **2026-07-09 Cascade (Open)**: The $7,550 PnL delta on this date is caused by CLOSE fills on a flat position after ghost OPEN removal — a source data integrity issue, not a classifier bug. The `file_audit.flagged` column will mark this file for manual review.
- **NQ Order Rejections (Jun 10-22, 2026)**: Sierra Chart rejected NQ orders due to symbol settings (`Trade Order Error`). These days have zero fills and are correctly handled as empty files.
- **Date Formatting**: GraphData files use `YYYY-M-D` (non-zero padded); requires ISO conversion before join with `clean_trades`.
- **Sim Accounts are stub-only**: `3Q_sim*`, `A_sim*`, `B_sim*` files are 178 bytes (header only) — parsed and audited as 0-fill files.
- **Staging only**: `trading_platform_clean_v2.db` is staging. Promotion to production requires explicit manual sign-off after reviewing flagged files.

---

## 21. Open Questions and Next Steps

1. **Review Flagged Files**: After cleaning completes, query `SELECT * FROM file_audit WHERE flagged=1 ORDER BY ABS(pnl_delta) DESC` and manually trace the top 10 by PnL delta.
2. **Promote to Production**: After sign-off on flagged files, migrate `clean_trades` → `processed_trades` in production DB.
3. **Live Ghost Monitor**: Implement real-time fill validation to detect un-tagged fills before DB insertion.
4. **Rolling OOS Selection**: Test rolling 90-day window slot selection to adapt to regime shifts.
5. **2026-07-09 Resolution**: Determine why CLOSE fills appear on a flat position — investigate Sierra Chart's Trade Evaluator behavior when a ghost OPEN is followed by a real strategy exit.

---

*Last Updated: August 2026 | SC Results WF Analytics Platform | GFRE v2*
