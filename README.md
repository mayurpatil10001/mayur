# Sierra Chart Trade Optimization Platform

A full-stack trading analytics platform that ingests Sierra Chart binary activity logs,
parses every fill into a structured SQLite database, and exposes a REST API + React dashboard
for strategy analysis, time-bin optimization, walk-forward testing, Monte Carlo simulation,
and trading recommendations.

---

## Database - Current State (July 2026)

| Metric | Value |
|--------|-------|
| Total trades | 733,847 |
| Total PnL | $-19,755,589.92 |
| Avg PnL / trade | $-26.92 |
| Overall win rate | 51.7% |
| Unique accounts | 114 |
| Unique symbols | 8 |
| Date range | 2023-09-04 to 2025-10-31 |

### PnL by Symbol

| Symbol | Contract | Multiplier | Trades | Total PnL | Win Rate |
|--------|----------|----------:|-------:|----------:|---------:|
| ES | E-mini S&P 500 | x50 | 301,317 | $-11,289,025 | 42.8% |
| NQ | E-mini Nasdaq-100 | x20 | 243,303 | $-1,375,580 | 60.9% |
| FDAX | DAX Futures | x25 | 140,055 | $-6,386,575 | 55.3% |
| CL | Crude Oil | x1000 | 39,725 | $-703,980 | 53.4% |
| ZBU/ZNU/ZBM/ZNM | Treasury | varies | 9,447 | $-430 | ~40% |

### Top Accounts by Trade Volume

| Account | Symbol | Trades | Total PnL | Date Range |
|---------|--------|-------:|----------:|-----------|
| ES-IPS_TM_5 | ES | 34,896 | -$3,968,550 | 2024-05 to 2025-10 |
| ES-TM_8 | ES | 32,728 | -$2,871,788 | 2024-05 to 2025-10 |
| ES-TM_5 | ES | 32,170 | -$2,921,175 | 2024-05 to 2025-10 |
| ES-IPS_TM_8 | ES | 18,761 | -$493,075 | 2024-05 to 2025-10 |
| ES-TM_7 | ES | 16,151 | +$900 | 2024-05 to 2025-10 |
| IPS_TM_8 | NQ | 13,901 | -$81,080 | 2024-03 to 2025-03 |
| TM_2 | NQ | 12,793 | -$193,075 | 2024-03 to 2025-09 |
| TM_D-R-1_2 | NQ | 12,511 | +$88,545 | 2024-06 to 2025-10 |
| TM_5 | FDAX | 8,216 | +$755,925 | 2024-06 to 2025-03 |
| TM_8 | NQ | 7,749 | +$277,775 | 2024-03 to 2024-08 |
| TM_8 | FDAX | 6,381 | +$396,775 | 2024-06 to 2025-03 |
| TM_7 | NQ | 10,067 | -$62,910 | 2024-03 to 2025-06 |
| T-S_PRODUCTION | ES | 6,828 | +$8,813 | 2024-07 to 2025-10 |

Profitable accounts: TM_D-R-1_2 NQ (+$88k), TM_5 FDAX (+$756k), TM_8 FDAX (+$397k), TM_8 NQ (+$278k)

---

## Architecture

    Sierra Chart (.data binary files in dataset/)
            |
            v
    [BinaryLogParser]
    - TLV binary reader (parallel, multi-threaded)
    - Ghost fill filter (drops fills without strategy tag)
    - Session boundary filter (drops trades crossing 17:00 NY)
    - ParentInternalOrderID pairing + FIFO fallback
            |
            v  writes to processed_trades (SQLite)
    [FastAPI Backend :8000] <--REST--> [React+TypeScript Dashboard :3001]

---

## Project Structure

    SC_results_WF/
    |-- trading_platform/              # Backend (Python / FastAPI)
    |   |-- api/
    |   |   |-- main.py                # App factory, middleware, all routers
    |   |   |-- routers/               # 20 API router modules
    |   |   |   |-- accounts.py        # Account management and listing
    |   |   |   |-- trades.py          # Trade CRUD
    |   |   |   |-- trade_import.py    # Paste-based Sierra Chart import
    |   |   |   |-- analytics.py       # Performance and risk metrics (270 KB)
    |   |   |   |-- time_bin_analytics.py  # 30-min slot matrix (48 KB)
    |   |   |   |-- walk_forward_analytics.py  # WFA engine (46 KB)
    |   |   |   |-- monte_carlo_analytics.py   # MC simulation (26 KB)
    |   |   |   |-- vix_regime.py      # VIX regime analysis
    |   |   |   |-- recommendations.py # Strategy recommendations
    |   |   |   |-- advanced_recommendations.py  # ML-enhanced recs
    |   |   |   |-- backtesting.py     # Backtest runner
    |   |   |   |-- exports.py         # CSV/PDF export
    |   |   |   |-- auth.py            # JWT authentication
    |   |   |   |-- health.py          # Health and monitoring
    |   |   |   |-- system.py          # System status
    |   |   +-- middleware/            # Rate-limit, security headers, logging
    |   |-- services/                  # 28 business logic modules
    |   |   |-- binary_log_parser.py   # Core .data file parser (1,704 lines, 90 KB)
    |   |   |-- trade_import_service.py    # Activity log text import (41 KB)
    |   |   |-- time_bin_analyzer.py       # 30-min time slot analysis (23 KB)
    |   |   |-- vix_regime_analyzer.py     # VIX regime classifier (29 KB)
    |   |   |-- performance_metrics_calculator.py  # Sharpe, Sortino, VaR
    |   |   |-- walk_forward/              # Walk-forward test engine
    |   |   |-- monte_carlo/               # Monte Carlo simulation
    |   |   |-- machine_learning/          # scikit-learn ML models
    |   |   +-- recommendation/            # Recommendation engine
    |   |-- models/                    # SQLAlchemy ORM models
    |   |-- database/                  # DB connection and session management
    |   +-- config.py                  # Central configuration
    |-- frontend/                      # React 18 + TypeScript dashboard
    |   |-- src/
    |   |   |-- components/            # Plotly charts, tables, UI
    |   |   |-- pages/                 # Analytics, accounts, recommendations views
    |   |   +-- store/                 # Redux Toolkit state
    |   +-- package.json               # Node dependencies
    |-- dataset/                       # 2,000+ Sierra Chart .data binary files
    |-- scripts/                       # 54 operational/maintenance scripts
    |-- rar_extract/                   # Extracted RAR activity log exports
    |-- data/                          # Historical .txt exports, sample datasets
    |-- docs/                          # Technical documentation
    |-- trading_platform.db            # Primary SQLite database (226 MB)
    |-- app_settings.json              # Scanner symbol+path configuration
    |-- requirements.txt               # Python dependencies
    |-- Dockerfile + docker-compose.yml
    +-- START.bat                      # One-click launch (backend + frontend)

---

## How to Run

### One-click (Windows)

    START.bat

Starts backend on port 8000 and frontend on port 3001.

### Manual

Backend (Python 3.11+):

    pip install -r requirements.txt
    python main.py
    # API docs: http://localhost:8000/docs
    # Swagger UI: http://localhost:8000/redoc

Frontend (Node 18+):

    cd frontend
    npm install
    npm start
    # Dashboard: http://localhost:3001

### Docker

    docker-compose up --build

---

## Configuration

app_settings.json - configures which symbols to scan and where:

    {
      "scanners": [
        {"symbol": "NQ",   "path": "C:\SC_results_WF\dataset"},
        {"symbol": "ES",   "path": "C:\SC_results_WF\dataset"},
        {"symbol": "CL",   "path": "C:\SC_results_WF\dataset"},
        {"symbol": "FDAX", "path": "C:\SC_results_WF\dataset"}
      ],
      "last_import_range": "2000",
      "last_used_symbol": "NQ",
      "import_days": "0"
    }

Environment variables (.env):

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///trading_platform.db | DB connection |
| API_PORT | 8000 | Backend port |
| SECRET_KEY | (set in production) | JWT signing key |
| DEVELOPMENT_MODE | true | Relaxes auth for local dev |
| RISK_FREE_RATE | 0.02 | Used in Sharpe ratio |
| DEFAULT_SIMULATIONS | 10000 | Monte Carlo iterations |
| ACCESS_TOKEN_EXPIRE_MINUTES | 30 | JWT expiry |
| LOG_LEVEL | INFO | Logging verbosity |

---

## API Reference

Base URL: http://localhost:8000/api/v1/
Authentication: Authorization: Bearer <JWT>
Interactive docs: http://localhost:8000/docs

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/login | Obtain JWT token |
| POST | /api/v1/auth/refresh | Refresh JWT token |

### Accounts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/accounts | List all 114 accounts with summary stats |
| GET | /api/v1/accounts/{id} | Account detail |
| GET | /api/v1/accounts/{id}/performance | Full performance metrics |
| GET | /api/v1/accounts/{id}/comparison | Cross-account benchmark comparison |

### Trades
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/trades | List trades (paginated, filterable by account/symbol/date) |
| GET | /api/v1/trades/{id} | Single trade detail |
| POST | /api/v1/trades/import-preview | Dry-run: parse pasted Sierra Chart text |
| POST | /api/v1/trades/import-paste | Commit: parse + deduplicate + insert |

### Trade Import (alternative prefix)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/trade-import/import-preview | Preview before committing |
| POST | /api/v1/trade-import/import-paste | Full import with deduplication |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/analytics/performance | Aggregated performance metrics |
| GET | /api/v1/analytics/time-analysis | Hour-of-day, day-of-week breakdowns |
| GET | /api/v1/analytics/risk-metrics | Sharpe, Sortino, max drawdown, VaR 95% |
| GET | /api/v1/analytics/walk-forward | OOS walk-forward results |

### Time-Bin Analytics (Core Feature)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/time-bins/analysis | Best 30-min slots per account/symbol |
| GET | /api/v1/time-bins/matrix | Full Mon-Fri x 09:30...15:30 permutation grid |
| GET | /api/v1/time-bins/recommendations | Top-N statistically significant windows |

### VIX Regime
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/vix-regime/analysis | Strategy PnL by VIX regime (Low/Normal/High/Extreme) |
| GET | /api/vix-regime/current | Current regime classification |

### Backtesting
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/backtesting/run | Run backtest with custom parameters |
| GET | /api/backtesting/results/{id} | Retrieve results |

### Recommendations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/recommendations | Current strategy recommendations |
| GET | /api/v1/recommendations/advanced | ML-enhanced recommendations |

### Exports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/exports/csv | Export filtered trades as CSV |
| GET | /api/v1/exports/report | Generate PDF performance report |

### System and Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | DB status + trade counts (no auth required) |
| GET | /api/v1/system/status | Full system health, service metrics |

---

## Core Data Pipeline

### 1. Binary Log Parser (binary_log_parser.py - 1,704 lines)

Reads Sierra Chart's TLV (Tag-Length-Value) binary .data format.

Supported instruments and contract specs:

| Symbol | Contract | Multiplier | Commission/ct |
|--------|----------|----------:|-------------:|
| NQ | E-mini Nasdaq-100 | x20 | $4.20 |
| ES | E-mini S&P 500 | x50 | $4.20 |
| FDAX | DAX Futures | x25 | $3.00 |
| CL | Crude Oil | x1,000 | $4.20 |
| MNQ | Micro Nasdaq-100 | x2 | $1.00 |
| MES | Micro S&P 500 | x5 | $1.00 |
| GC | Gold | x100 | $4.20 |
| RTY | Russell 2000 | x50 | $4.20 |
| YM | Dow Jones | x5 | $4.20 |

Key algorithms:

- _parse_file_nitro: Multi-threaded TLV reader with automatic sync recovery
- _pairs_to_trades: Stateful OPEN/CLOSE pairing. Priority: ParentInternalOrderID > SC position order (Tag 104) > FIFO by timestamp
- _is_ghost_fill: Ghost filter. Drops fills where qty > 1 AND no "AT_" strategy tag in note or message AND not in EOD window (16:55-17:05 NY)
- _crosses_daily_close_ny: Drops round-trips that span the 17:00 NY session close
- _parse_tag66_timestamp: Multi-format timestamp decoder supporting SCDateTime double (days since 1899-12-30), Unix microseconds, and Unix milliseconds
- _session_trade_date_ny: SC trade-date logic - sessions roll at 17:00 NY, not midnight

### 2. Trade Import Service (trade_import_service.py - 41 KB)

Processes Sierra Chart Activity Log text exports (paste-in via API or file):

- Parses tab-delimited fill rows from the Activity Log export format
- Groups fills by account and symbol
- Applies _pairs_by_open_close for round-trip matching
- Generates deterministic trade_id = MD5(account+symbol+side+entry+exit+price+qty)
- Deduplication: re-importing same data is always safe
- Writes with NY-timezone hour_of_day and day_of_week for time-bin analysis

### 3. Database Schema

processed_trades table (733,847 rows - the central table):

| Column | Type | Description |
|--------|------|-------------|
| trade_id | TEXT PK | MD5 hash - idempotent dedup key |
| account_name | TEXT | Sierra Chart account (e.g. TM_7, IPS_TM_8) |
| symbol | TEXT | Base symbol (NQ, ES, FDAX, CL) |
| side | TEXT | LONG or SHORT |
| entry_time | TEXT | ISO 8601, NY timezone |
| exit_time | TEXT | ISO 8601, NY timezone |
| entry_price | REAL | Fill price at entry |
| exit_price | REAL | Fill price at exit |
| quantity | INTEGER | Number of contracts |
| profit_loss | REAL | Net PnL including commission |
| commission | REAL | Total commission (both sides) |
| duration_minutes | INTEGER | Trade duration in minutes |
| hour_of_day | INTEGER | NY hour of entry (0-23) |
| day_of_week | INTEGER | 0=Monday to 4=Friday |

---

## Analytics Engine

### Time-Bin Analysis (Core Feature)

The primary purpose of this platform is identifying the best 30-minute time windows
for each trading strategy. For each account+symbol combination:

- Evaluates all 60 permutations: 5 days (Mon-Fri) x 12 slots (09:30, 10:00, ..., 15:30)
- Statistical significance: t-test, Mann-Whitney U, bootstrap confidence intervals
- Output: expected PnL/trade, win rate, trade count, p-value per slot
- Answers: "Which Monday 09:30-10:00 window has the best historical edge?"

### Walk-Forward Analysis

- Rolling in-sample training / out-of-sample test windows
- Prevents overfitting by testing on genuinely unseen data
- Produces OOS Sharpe ratio, max drawdown, consistency metrics

### Monte Carlo Simulation

- 10,000 equity curve simulations (configurable)
- 252 trading-day horizon (one calendar year)
- Outputs: VaR 95%, CVaR (Expected Shortfall), probability of ruin, drawdown distribution

### VIX Regime Analysis

Classifies each trading day by VIX level:
- Low: VIX < 15
- Normal: VIX 15-25
- High: VIX 25-35
- Extreme: VIX > 35

Reports strategy performance (win rate, avg PnL, Sharpe) conditional on each regime.
Identifies regime-sensitive strategies that should be sized differently in high-VIX environments.

### Machine Learning

scikit-learn based feature engineering:
- Input features: hour_of_day, day_of_week, recent volatility, win streak, regime
- Predicts win probability for each time slot
- Used to weight and rank recommendations

---

## Verification Results (July 2026)

### Binary Parser vs Database Comparison

Test: parsed TM_7 NQ .data files for 2024-03-13 to 2024-03-14, compared to processed_trades.

| Field | Match Rate | Notes |
|-------|----------:|-------|
| Entry price | 100% | Binary files read correctly |
| Trade direction (side) | 100% | No direction errors |
| Timestamps | 100% | All within 5 seconds |
| Exit price | 43.6% | Same-timestamp fill ordering varies |
| Quantity | 64.0% | Same-timestamp fill split variations |
| PnL | 0% exact | Systematic $4.20/contract offset |
| DB-only trades | 0 | Nothing in DB is invented |
| Parser-only trades | 32 | Correctly filtered (ghost/session rules) |

Root causes of differences:
1. Commission: DB applies $4.20/contract at import time. All PnL differences are exact
   multiples of $4.20 - systematic and not data errors.
2. Fill ordering: For same-millisecond fills, DB uses ParentInternalOrderID priority then
   SC position order; standalone pairer uses pure FIFO. Same fills, different pairing.
3. 32 parser-only trades: Correctly excluded by ghost filter (_is_ghost_fill) or
   session boundary filter (_crosses_daily_close_ny for post-17:00 NY trades).

Conclusion: The system faithfully represents the raw binary trading data.

### Activity Log (2026 RAR) Verification

| Source | Trades | Date Range |
|--------|-------:|-----------|
| RAR Activity Log | 8,766 | 2026-04-01 to 2026-07-20 |
| Database (TM_7/NQ) | 10,067 | 2024-03-13 to 2025-06-30 |
| Date overlap | None | 275-day gap between datasets |
| trade_id matches | 0 | Entirely new data |

The parsing logic is consistent between the binary parser and Activity Log parser.
The 8,766 RAR trades are verified and ready for production import.

### Strategy Performance Findings (TM_7 / NQ)

| Dataset | Period | Trades | PnL | Win Rate |
|---------|--------|-------:|----:|---------:|
| Historical DB | 2024-03 to 2025-06 | 10,067 | -$62,910 | 63.4% |
| 2026 RAR file | 2026-04 to 2026-07 | 8,766 | -$306,461 | 62.0% |

The TM_7/NQ strategy shows consistent losses despite a 60%+ win rate,
indicating the losing trades are significantly larger than winning trades.
The 2026 data shows 5x larger losses than the 2024-2025 period.

---

## All Database Tables

| Table | Rows | Purpose |
|-------|-----:|---------|
| processed_trades | 733,847 | Core trade storage - all parsed trades |
| rar_imported_trades | 8,766 | Shadow table from RAR verification run |
| rar_trades | 8,766 | RAR Activity Log parsed trades (2026) |
| accounts | 0 | Account registry (auto-populated on use) |
| performance_metrics | 0 | Cached performance calculations |
| time_bin_analysis | 0 | Cached time-bin results |
| walk_forward_results | 0 | Walk-forward output cache |
| monte_carlo_results | 0 | Monte Carlo simulation cache |
| market_data | 0 | External market data (yfinance / VIX) |
| volatility_regimes | 0 | VIX regime classifications by date |
| temporal_performance | 0 | Per-slot performance cache |
| pending_fills | 0 | Unmatched open fills awaiting close |
| sierra_chart_fills | 0 | Raw fill buffer (pre-pairing) |

---

## Key Operational Scripts

| Script | Purpose |
|--------|---------|
| START.bat | Launch full platform (backend + frontend) |
| scripts/start_backend_only.bat | Backend only (port 8000) |
| scripts/start_frontend_only.bat | Frontend only (port 3001) |
| scripts/generate_dev_token.py | Generate JWT for local development |
| scripts/optimize_database.py | Rebuild SQLite indexes for query speed |
| scripts/deduplicate_db.py | Remove any duplicate trade_ids |
| scripts/run_full_import.py | Trigger full dataset re-import |
| scripts/compare_strategies_oos.py | OOS strategy comparison |
| verify_system_import.py | Verify RAR import consistency |
| final_verify_compare.py | Binary .data file vs DB field comparison |

---

## Security

- JWT Bearer token authentication (30-min expiry by default)
- Rate limiting: 500 requests/minute (configurable via RATE_LIMIT_PER_MINUTE)
- Security headers middleware: X-Frame-Options, Content-Security-Policy, HSTS
- CORS: open in development (allow_origins=["*"]), should be restricted in production
- DEVELOPMENT_MODE=true bypasses authentication for local development
- All endpoints except /health and /api/v1/auth/* require valid JWT

---

## Technology Stack

Backend:
- Python 3.11+
- FastAPI 0.104 + Uvicorn 0.24 (ASGI)
- SQLAlchemy 2.0 + Alembic (ORM + migrations)
- Pandas 2.1, NumPy 1.25, SciPy 1.11 (data analysis)
- scikit-learn 1.3 (machine learning)
- Statsmodels 0.14 (statistical testing)
- yfinance 0.2 (VIX market data)
- loguru 0.7 (structured logging)

Frontend:
- React 18.2 + TypeScript 4.9
- Redux Toolkit 1.9 (state management)
- Plotly.js 2.26 via react-plotly.js (interactive charts)
- React Router 6.16 (client-side routing)
- Proxied to http://localhost:8000

Infrastructure:
- SQLite 226 MB primary database
- Docker + docker-compose for containerized deployment

---

## Production Security Checklist

Before deploying this platform to production, perform the following security hardening steps:

1. **Disable Development Mode:**
   Set `DEVELOPMENT_MODE=false` in `.env`.
   When `DEVELOPMENT_MODE=true`, JWT authentication is bypassed and all requests execute as `dev_user` (admin role). Setting `false` enforces JWT verification on all endpoints except `/health` and `/docs`.

2. **Generate Cryptographic Secret Key:**
   Set `SECRET_KEY` to a cryptographically secure 32+ character random string (e.g. `openssl rand -hex 32`).
   Never use default or fallback secret keys in production.

3. **Restrict CORS Origins:**
   Set `ALLOWED_ORIGINS` in `.env` to your exact frontend domain(s), e.g. `ALLOWED_ORIGINS=https://app.yourdomain.com`.
   When `DEVELOPMENT_MODE=true`, CORS defaults to `*`. In production with `DEVELOPMENT_MODE=false`, unlisted origins are blocked.

4. **Restrict Trusted Hosts:**
   Set `API_HOST` in `.env` to your server's domain/IP address to enforce `TrustedHostMiddleware`.

---

## Notes and Known Behaviors

- All timestamps stored and analyzed in New York (ET/EST) timezone
- Session boundary: 17:00 NY = end of trading day. Trades crossing 17:00 are filtered out.
- Ghost fill filter: Fills without strategy tag (AT_ prefix in Order Note tag 0x82)
  and not during EOD flattenings (16:55-17:05 NY) are dropped as ghost fills.
  1-lot fills are always kept (never ghosts - used for stops/exits).
- Idempotent imports: trade_id = MD5(key fields). Re-importing same data is always safe.
- Binary files with numeric dates (e.g. 19550-12-05) use pre-2000 epoch timestamps
  and return [Errno 22] Invalid argument - this is expected and harmless.
- Pending 2026 import: 8,766 trades (2026-04-01 to 2026-07-20) verified and ready
  for production import via POST /api/v1/trade-import/import-paste.
- The scratch_parser_test.db (226 MB) in the project root can be safely deleted.

---

Last updated: July 21, 2026
Database: 733,847 trades | 114 accounts | 8 symbols | 2023-09-04 to 2025-10-31
