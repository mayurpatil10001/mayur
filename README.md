# Sierra Chart Trade Optimization & Analytics Platform (`SC_results_WF`)

> **A production-grade, multi-account quantitative trading analytics platform** that parses raw Sierra Chart (SC) binary trade activity logs (`.data` files in proprietary TLV format), eliminates platform-level execution corruption via the **Ghost Fill Resynchronization Engine (GFRE)**, stores strategy-attributed trades in a SQLite database, and evaluates time-of-day statistical edge (Benjamini-Hochberg FDR correction, out-of-sample audits, permutation tests).

---

## 🚀 Key Updates & Current Status (July 2026)

### 1. Ghost Fill Resynchronization Engine (GFRE) Integration
- **Engine Status**: **LIVE & DEPLOYED** in `trading_platform/services/ghost_fill_engine.py` and `binary_log_parser.py`.
- **Database Sanitization**: **~606,856 phantom trade records purged** across all accounts (TM_1 to TM_10, V_sim, TS, IPS, 3Q_sim) and assets (FDAX, NQ, ES, CL).
- **Core Breakthrough**: Isolated and eliminated Sierra Chart's internal Trade Evaluator un-tagged fills (ghost fills) that caused downstream direction-flip cascades.
- **Empirical Validation**: Achieved **100% clean position resynchronization** (0 direction flips, 0 position leaks at session boundaries) across sample windows, high-volume fast days (1,000+ fills/day), and full date range audits.

### 2. NQ Empirical Comparison Case Study (June 10 – July 23, 2026)
A 22-active-day side-by-side audit comparing raw un-filtered data (*Dirty*) vs. GFRE resynchronized data (*Clean*):

| Metric | Dirty Baseline (Unfiltered) | GFRE Clean (Sanitized) | Impact / Insight |
| :--- | ---: | ---: | :--- |
| **Total Realized PnL ($)** | +$18,800.00 | **-$3,925.00** | ❌ -$22,725.00 overstatement removed |
| **Executed Trade Count** | 898 | **849** | -49 phantom/fragmented trades purged |
| **Win Rate (%)** | 67.4% | **58.9%** | -8.5pp (unmasked false win bias) |
| **Max Drawdown ($)** | $38,970.00 | **$65,885.00** | Revealed true drawdown risk |
| **Ghost Fills Dropped** | 0 | **33** | 100% tag-less Evaluator fills purged |
| **Direction Flips** | ~33 cascades | **0** | All position state corruption eliminated |
| **Session Integrity Pass Rate** | 68% | **100% (22/22 days)** | Position flat at session close every day |

> **Verdict**: The GFRE performed flawlessly technically (100% integrity pass). It revealed that un-filtered binary log data gave a false +$18.8k impression due to ghost fill position resets, whereas the true strategy execution during this window was -$3.9k.

---

## ⚠️ Statistical & Out-of-Sample Edge Summary

While the data layer and parser are now 100% sanitized, statistical edge testing yields the following honest findings:

1. **Out-of-Sample (OOS) Audit (`2025-01-01 to 2025-10-31`)**:
   - In-sample (train): +$676k profit on BH-FDR time-slot selection.
   - Out-of-sample (test): **-$117,987.50 loss** (Profit Factor 0.79, Sharpe Ratio -0.88).
   - *Conclusion*: Time-of-day slots exhibit non-stationarity across market regimes.

2. **Permutation Noise Test (1,000 Iterations)**:
   - In-sample selection is statistically distinct from pure noise ($p < 0.05$), but noise alone generates ~$261k in false-positive in-sample PnL due to multiple-comparisons fitting.

---

## 🏗️ Architecture & Pipeline Overview

```text
       Sierra Chart Platform (C++ DLL AutoTrader Studies)
                               │
                               ▼
     Raw Binary Activity Logs (dataset/*.data TLV Format)
                               │
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │             binary_log_parser.py (_parse_file_nitro)   │
   │                                                        │
   │   ┌────────────────────────────────────────────────┐   │
   │   │  Ghost Fill Resynchronization Engine (GFRE)    │   │
   │   │  (ghost_fill_engine.py)                        │   │
   │   │                                                │   │
   │   │  Stage 1: Tag-Validation Filter (_is_ghost)    │   │
   │   │  Stage 2: Adaptive Bypass (_compute_note_rate) │   │
   │   │  Stage 3: Per-Batch Dedup (_dedup_fills)       │   │
   │   │  Stage 4: FIFO Resynchronizer (pair_fills)     │   │
   │   │  Stage 5: Integrity Verifier (verify_seq)      │   │
   │   └────────────────────────────────────────────────┘   │
   └───────────────────────────┬────────────────────────────┘
                               │ Writes Clean Trades
                               ▼
        SQLite Database (trading_platform.db: processed_trades)
                               │
                               ▼
            FastAPI Backend (http://localhost:8000)
                               │
                               ▼
       React 18 + TypeScript Dashboard (http://localhost:3000)
```

---

## 👻 The Ghost Fill Problem & GFRE Solution

### What is a Ghost Fill?
A **Ghost Fill** is an execution record logged in Sierra Chart binary `.data` files that **lacks the C++ strategy attribution tag** (Tag `0x82` / `AutoTrader_` note). 

### Root Cause
Sierra Chart's internal **Trade Evaluator** engine evaluates limit/stop target fills without forwarding the C++ DLL study's custom order note. These tag-less records cause the parser to force-close active positions, making the strategy hold reverse-direction positions on subsequent signals (a *direction flip cascade*).

### GFRE 5-Stage Resynchronization Pipeline

1. **Stage 1 — Tag-Validation Filter (`classify_fill`)**: Drops fills lacking Tag `0x82` strategy notes when logged by the SC Trade Evaluator. Exempts 1-lot orders and EOD flattenings (16:55–17:05 NY).
2. **Stage 2 — Adaptive Bypass (`_compute_note_rate`)**: If <25% of fills carry notes (e.g., account setups like TM_10), ghost filtering automatically bypasses to prevent false drops.
3. **Stage 3 — Per-Batch Deduplication (`_dedup_fills`)**: Collapses duplicate records emitted within 250ms, preserving the note-bearing version.
4. **Stage 4 — FIFO Position Resynchronizer (`pair_fills_to_trades`)**: Rebuilds clean entry/exit trades using Sierra Chart's exact execution sequence (`_position_order`).
5. **Stage 5 — Sequence Integrity Verifier (`verify_sequence`)**: Confirms 0 net position drift at session close and 0 direction flips remaining.

---

## 📊 Account & Asset Map

The system parses raw binary logs across multiple trading accounts and assets:

| Suffix | Primary Asset | Description |
| :--- | :--- | :--- |
| `.TM_7.data` | FDAX | DAX Futures (EUR 25/pt) |
| `.IPS_TM_7.data` | NQ, CL | Nasdaq-100 ($20/pt) & Crude Oil ($1000/pt) |
| `.ES-TM_7.data` / `.ES-IPS_TM_7.data` | ES | S&P 500 E-mini ($50/pt) |
| `TM_1` – `TM_10` | Multi | Primary strategy accounts |
| `V_sim1` – `V_sim16` | Multi | Virtual simulation accounts |
| `TS_2` – `TS_7` | Multi | Test strategy accounts |

---

## 📁 Key Project Files & Reference

| File | Description |
| :--- | :--- |
| **[`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)** | **Primary technical reference document** — full TLV binary tag spec, database schema, and detailed GFRE history. |
| [`trading_platform/services/ghost_fill_engine.py`](trading_platform/services/ghost_fill_engine.py) | Standalone GFRE module (5-stage pipeline, dataclass models). |
| [`trading_platform/services/binary_log_parser.py`](trading_platform/services/binary_log_parser.py) | Core TLV parser, multi-core batch processing, database handler. |
| [`scripts/nq_gfre_comparison.py`](scripts/nq_gfre_comparison.py) | Full 22-day NQ dirty vs clean comparison script. |
| [`scripts/full_signal_fill_sync.py`](scripts/full_signal_fill_sync.py) | 31-day GraphData signal-to-fill matching script. |
| [`docs/nq_gfre_comparison_jun10_jul23.csv`](docs/nq_gfre_comparison_jun10_jul23.csv) | Full NQ dirty vs clean day-by-day comparison CSV export. |
| [`docs/tm7_nq_full_signal_fill_sync.csv`](docs/tm7_nq_full_signal_fill_sync.csv) | Day-by-day signal match rate report. |

---

## 🛠️ How to Run

### Quick Start (Windows)
```cmd
START.bat
```
Launches backend (`http://localhost:8000`) and frontend (`http://localhost:3000`).

### Backend Only
```cmd
scripts\start_backend_only.bat
```

### Manual Setup
```bash
cp .env.example .env
pip install -r requirements.txt
python main.py
```

### Run GFRE Comparison Audit
```bash
python scripts/nq_gfre_comparison.py
```

### Run Automated Tests
```bash
pytest
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, SQLite3, asyncio, concurrent.futures
- **Analytics**: Pandas, NumPy, SciPy, Statsmodels
- **Frontend**: React 18, TypeScript, Redux Toolkit, Plotly.js
- **Data Format**: Sierra Chart TLV Binary (`.data`), CSV exports (`GraphData.txt`)

---

*Last Updated: July 2026 | SC Results WF Analytics Platform*
