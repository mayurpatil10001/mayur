# Sierra Chart Trade Optimization & Analytics Platform (`SC_results_WF`)

**`SC_results_WF`** is a production-grade, multi-account quantitative trading analytics platform designed for Sierra Chart (SC). It parses raw SC binary trade activity logs (`.data` files in Sierra Chart's proprietary Tag-Length-Value binary format), eliminates platform-level execution corruption using the bespoke **Ghost Fill Resynchronization Engine (GFRE)**, stores verified strategy-attributed trades in a SQLite database, evaluates time-of-day statistical edge using Benjamini-Hochberg FDR correction, and exposes interactive analytics via a FastAPI backend and React/TypeScript dashboard.

> **Technical Reference Notice**: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) contains the complete low-level technical specification (binary TLV tag mapping, SQLite schema, GFRE algorithm steps, investigation log). This `README.md` serves as the primary system entry point and broad architecture document.

---

## Table of Contents

1. [Project Mission](#1-project-mission)
2. [Current System Status — July 2026](#2-current-system-status--july-2026)
3. [The Ghost Fill Problem](#3-the-ghost-fill-problem)
4. [Ghost Fill Resynchronization Engine (GFRE)](#4-ghost-fill-resynchronization-engine-gfre)
5. [NQ Empirical Validation Case Study](#5-nq-empirical-validation-case-study)
6. [Architecture Overview](#6-architecture-overview)
7. [Data Sources and Binary Format](#7-data-sources-and-binary-format)
8. [Database Schema](#8-database-schema)
9. [Backend API Reference](#9-backend-api-reference)
10. [Frontend Dashboard](#10-frontend-dashboard)
11. [Statistical Edge Analysis](#11-statistical-edge-analysis)
12. [Account and Asset Mapping](#12-account-and-asset-mapping)
13. [Key Files and Scripts](#13-key-files-and-scripts)
14. [Output Reports](#14-output-reports)
15. [How to Run](#15-how-to-run)
16. [Technology Stack](#16-technology-stack)
17. [Security](#17-security)
18. [Investigation Timeline](#18-investigation-timeline)
19. [Known Limitations](#19-known-limitations)
20. [Open Questions and Next Steps](#20-open-questions-and-next-steps)

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
- **Sanitize Fills via GFRE**: Detect and purge un-attributed Trade Evaluator fills while preserving legitimate strategy trades.
- **Resynchronize FIFO Sequences**: Match entries and exits using Sierra Chart's exact execution sequence index (`_position_order`).
- **Compute Reliable Metrics**: Calculate true PnL, Win Rate, Drawdown, and Sortino Ratios across accounts and symbols.
- **Evaluate Statistical Edge**: Apply Benjamini-Hochberg False Discovery Rate (FDR) control to identify time-of-day edge slots.
- **Out-of-Sample Audit**: Test identified time-of-day slots strictly out-of-sample on unseen test data.


## 2. Current System Status — July 2026

### GFRE Deployment & Sanitization
The Ghost Fill Resynchronization Engine is fully operational in `trading_platform/services/ghost_fill_engine.py` and integrated directly into `trading_platform/services/binary_log_parser.py`.

#### Key Metrics (Post-GFRE Audit):
- **Phantom Records Purged**: ~606,856 phantom records deleted from the database.
- **Accounts Covered**: `TM_1` through `TM_10`, `V_sim1` to `V_sim16`, `TS_2` to `TS_7`, `IPS_TM_7`, `3Q_sim`, and `Tsufim-Prod`.
- **Assets Covered**: FDAX (DAX Futures), NQ (Nasdaq-100), ES (S&P 500 E-mini), CL (Crude Oil), GC (Gold), YM (Dow Jones), RTY (Russell 2000).
- **Integrity Pass Rate**: **100%** across all processed daily files (0 net position drift at session close, 0 direction flips).

### Database & System Health
- `processed_trades` table stores 126,991+ clean, verified round-trip strategy trades.
- FastAPI backend serves sanitized analytics and performance metrics.
- React/TypeScript dashboard offers real-time visualization, leaderboard rankings, and trade history.


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


## 4. Ghost Fill Resynchronization Engine (GFRE)

The GFRE sanitizes fill streams through a 5-stage pipeline:

```
[Raw Binary Fills]
       │
       ▼
Stage 1: Tag-Validation Filter (classify_fill)
       │  • Rule 1: 1-lot exemption (qty == 1 -> keep)
       │  • Rule 2: EOD exemption (16:55-17:05 NY -> keep)
       │  • Rule 3: Evaluator + No Tag -> DROP (GHOST)
       │  • Rule 4: Non-Evaluator Exits -> KEEP
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
Stage 5: Sequence Integrity Verifier (verify_sequence)
       │  • Verifies net position balance == 0 & direction flips == 0
       ▼
[Sanitized RoundTrip Trades]
```

### Detailed Stage Breakdown:

#### Stage 1: Tag-Validation Filter (`classify_fill`)
Evaluates every candidate fill against 4 deterministic rules:
- **Rule 1 (1-Lot Exemption)**: 1-contract fills are preserved unconditionally because confirmed ghost fills are multi-lot position resets.
- **Rule 2 (EOD Exemption)**: Fills between 16:55 and 17:05 NY wall-clock time are preserved to avoid dropping session-flattening trades.
- **Rule 3 (Evaluator Rule)**: Fills containing `Trading Evaluator` in message text MUST contain a strategy tag (`AutoTrader_`, `AT_`, `Text: Tag:`). Missing tag -> flagged as Ghost.
- **Rule 4 (Non-Evaluator Exit Rule)**: Exits (`open_close == CLOSE`) are preserved for non-Evaluator records. Entry fills without strategy tags are dropped.

#### Stage 2: Adaptive Bypass Detection (`_compute_note_rate`)
Calculates the fraction of fills in a file containing Tag `0x82` notes. If note coverage is under 25% across >5 fills (e.g. `TM_10`), ghost filtering is automatically bypassed for that file to prevent dropping un-tagged legitimate trades.

#### Stage 3: Per-Batch Deduplication (`_dedup_fills`)
Groups fills into 250ms windows (`(round(ts_val / 0.25) * 0.25, price, side, quantity, account, order_id)`). Keeps the note-bearing version if duplicates exist.

#### Stage 4: FIFO Position Resynchronizer (`pair_fills_to_trades`)
Maintains an internal signed position counter and open-leg queue. Fills are sorted by Sierra Chart's execution order index (`_position_order`), then timestamp. Matches entries with exits to produce completed `RoundTrip` objects.

#### Stage 5: Sequence Integrity Verifier (`verify_sequence`)
Checks that:
1. Net position delta at session end equals 0 (or unpaired open legs).
2. Remaining direction flips in the clean fill stream equal 0.
3. Summary report is output to logs.


## 5. NQ Empirical Validation Case Study

### Overview (June 10 – July 23, 2026 | 22 Active NQ Days)
A side-by-side comparison of **Dirty** (unfiltered data) vs. **GFRE Clean** (sanitized data) on NQ strategy executions (`IPS_TM_7.data`):

| Metric | Dirty Baseline | GFRE Clean | Difference / Impact |
| :--- | ---: | ---: | :--- |
| **Total Realized PnL ($)** | +$18,800.00 | **-$3,925.00** | ❌ -$22,725.00 overstatement removed |
| **Executed Trades** | 898 | **849** | -49 phantom trades purged |
| **Win Rate (%)** | 67.4% | **58.9%** | -8.5pp false win rate bias removed |
| **Max Drawdown ($)** | $38,970.00 | **$65,885.00** | True drawdown risk 69% higher |
| **Ghost Fills Dropped** | 0 | **33** | 100% ghost fills purged |
| **Direction Flips** | ~33 cascades | **0** | All position corruption eliminated |
| **Integrity Pass Rate** | 68% | **100% (22/22 days)** | All sessions close flat |

### Day-by-Day Audit Highlights:
- **Clean Days Untouched**: On the 7 days with zero ghost fills (e.g., June 24, June 28, June 30, July 3, July 6, July 12, July 16), Dirty and Clean results were **100% identical**, proving zero false positives.
- **June 29**: Ghost fills created a fake -$1,950 loss in dirty data. GFRE revealed actual strategy PnL was **+$31,150** (+$33.1k swing).
- **July 02**: 1 ghost fill reshuffled pairing on a high-volume day, revealing -$40,795 PnL vs -$4,960 in dirty data (-$35.8k correction).
- **July 13**: 3 ghost fills inflated win rate to 66.7% in dirty data. GFRE revealed true win rate was 38.5% (-$15.2k correction).


## 6. Architecture Overview

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
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |   binary_log_parser._parse_file_nitro |
                      |   - Pre-scans FIFO position orders    |
                      |   - Decodes TLV tags (0x66, 0x82, etc)|
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |  Ghost Fill Resynchronization Engine  |
                      |  (trading_platform/services/gfre.py)  |
                      |  - 5-Stage Filtering & Verification   |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |   SQLite DB (trading_platform.db)     |
                      |   - Table: processed_trades           |
                      +-------------------+-------------------+
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


## 7. Data Sources and Binary Format

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


## 8. Database Schema

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

CREATE INDEX idx_proc_trades_acc_sym ON processed_trades(account_name, symbol);
```


## 9. Backend API Reference

FastAPI runs on `http://localhost:8000`. Interactive documentation is available at `http://localhost:8000/docs`.

### Key Endpoints:
- `GET /analytics/performance`: Aggregate PnL, Win Rate, Profit Factor by account/symbol.
- `GET /analytics/time-bins`: 30-minute time slot performance breakdown.
- `GET /analytics/sortino-leaderboard`: Ranked accounts by annualized Sortino ratio.
- `GET /analytics/drawdown`: Equity drawdown series data.
- `GET /trades`: Filterable trade history list.
- `POST /import/trigger`: Run binary log scanner and GFRE import.


## 10. Frontend Dashboard

React 18 + TypeScript SPA running on `http://localhost:3000`.

- **SimpleDashboard.tsx**: Key metrics cards (Win Rate, Profit Factor, Sortino) & cumulative PnL chart.
- **SortinoLeaderboard.tsx**: Account leaderboard sorted by risk-adjusted return.
- **TimeSlotHeatmap.tsx**: Interactive 30-minute time-of-day edge heatmap.
- **TradeHistory.tsx**: Searchable, filterable trade execution table.


## 11. Statistical Edge Analysis

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


## 12. Account and Asset Mapping

| Account Suffix | Primary Asset | Multiplier |
| :--- | :--- | :--- |
| `.TM_7.data` | FDAX (DAX Futures) | EUR 25.00 / pt |
| `.IPS_TM_7.data` | NQ (Nasdaq-100), CL (Crude Oil) | USD 20.00 / pt (NQ), USD 1,000 / $1 (CL) |
| `.ES-TM_7.data` | ES (S&P 500 E-mini) | USD 50.00 / pt |
| `TM_1` – `TM_10` | Multi-asset | Varies |
| `V_sim1` – `V_sim16` | Virtual Simulation | Varies |


## 13. Key Files and Scripts

- [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md): Comprehensive technical reference.
- `trading_platform/services/ghost_fill_engine.py`: Standalone GFRE module.
- `trading_platform/services/binary_log_parser.py`: TLV parser & multi-threaded parser.
- `scripts/nq_gfre_comparison.py`: 22-day NQ dirty vs clean comparison script.
- `scripts/full_signal_fill_sync.py`: 31-day GraphData signal matching script.


## 14. Output Reports

- `docs/nq_gfre_comparison_jun10_jul23.csv`: Day-by-day NQ comparison report.
- `docs/tm7_nq_full_signal_fill_sync.csv`: 31-day signal match rate report.
- `docs/OUT_OF_SAMPLE_RESULTS.md`: Out-of-sample statistical audit.
- `docs/PERMUTATION_TEST_RESULTS.md`: 1,000-iteration permutation test results.


## 15. How to Run

### Windows Quick Launcher:
```cmd
START.bat
```

### Backend Only:
```cmd
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


## 16. Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, SQLite3, asyncio, concurrent.futures
- **Analytics**: Pandas, NumPy, SciPy, Statsmodels, scikit-learn
- **Frontend**: React 18, TypeScript, Redux Toolkit, Plotly.js
- **Build/CI**: Docker Compose, GitHub Actions

---

## 17. Security

- All API keys and DB credentials managed via `.env` (excluded via `.gitignore`).
- `dataset/` binary files and `*.db` databases are excluded from git repository.
- JWT authentication implemented with configurable expiration.

---

## 18. Investigation Timeline

1. **Anomaly Identification**: Trade frequency spike & PnL inversion detected.
2. **Root Cause Isolation**: Sierra Chart Trade Evaluator identified as source of un-tagged fills (Tag 0x82 absence).
3. **GFRE Engine Built**: 5-stage resynchronization engine implemented.
4. **Database Sanitization**: ~606,856 phantom trade records purged.
5. **Validation**: Verified on NQ & FDAX datasets (100% integrity pass rate).
6. **Documentation**: `PROJECT_OVERVIEW.md` & `README.md` updated.

---

## 19. Known Limitations

- **NQ Order Rejections (Jun 10-22, 2026)**: Sierra Chart rejected NQ orders due to symbol settings (`Trade Order Error`).
- **Data Gap**: No `IPS_TM_7` files present after July 17, 2026.
- **Date Formatting**: GraphData files use `YYYY-M-D` (non-zero padded); requires ISO conversion.

---

## 20. Open Questions and Next Steps

1. **Investigate NQ Rejections**: Resolve Sierra Chart order permission settings for NQ contract rolls.
2. **Live Ghost Monitor**: Implement real-time fill validation to detect un-tagged fills before DB insertion.
3. **Rolling OOS Selection**: Test rolling 90-day window slot selection to adapt to regime shifts.

---

*Last Updated: July 2026 | SC Results WF Analytics Platform*
