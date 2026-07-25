# 🏁 SC_results_WF — Complete Project Deep Dive

## What Is This Project?

This is a **full-stack algorithmic trading analytics platform** built to ingest, analyze, and optimize real futures trading data exported from **Sierra Chart** (a professional trading platform). It is NOT a live trading bot — it is a **post-trade intelligence engine** that tells a trader *when to trade*, *which accounts perform best*, and *how to size positions* based on deep historical analysis.

The project name `SC_results_WF` stands for **SierraChart Results — Walk Forward**.

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Sierra Chart                        │
│      (Trading Platform — generates .txt/.bin logs)      │
└───────────────────────┬─────────────────────────────────┘
                        │ Raw trade exports
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Data Ingestion Layer                        │
│   binary_log_parser.py | trade_import_service.py        │
│   sierra_chart_parser.py | processed_trade_parser.py    │
└───────────────────────┬─────────────────────────────────┘
                        │ Normalized trades
                        ▼
┌─────────────────────────────────────────────────────────┐
│              SQLite Database (trading_platform.db)       │
│              Managed by SQLAlchemy + Alembic             │
└───────────────────────┬─────────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
┌─────────────────────┐  ┌────────────────────────────┐
│   Analytics Engine  │  │    ML / Simulation Engine  │
│   time_bin_analyzer │  │  machine_learning/          │
│   vix_regime_analyz │  │  monte_carlo/               │
│   temporal_analysis │  │  walk_forward/              │
│   performance_calc  │  │  recommendation/            │
└─────────┬───────────┘  └────────────┬───────────────┘
          │                           │
          └──────────┬────────────────┘
                     ▼
        ┌────────────────────────┐
        │   FastAPI REST API     │
        │   (trading_platform/   │
        │    api/)               │
        └────────────┬───────────┘
                     │ HTTP / JSON
                     ▼
        ┌────────────────────────┐
        │  React + TypeScript    │
        │  Dashboard (frontend/) │
        │  Plotly.js charts      │
        │  Redux Toolkit state   │
        └────────────────────────┘
```

---

## 📁 Root-Level Files

| File | Purpose |
|------|---------|
| [main.py](file:///d:/SC_results_WF/main.py) | **Entry point** — starts the Uvicorn/FastAPI server |
| [trading_platform/config.py](file:///d:/SC_results_WF/trading_platform/config.py) | **Global config** — paths to SierraChart data folders, DB URL, JWT secret, Monte Carlo params, rate limits |
| [requirements.txt](file:///d:/SC_results_WF/requirements.txt) | Python dependency manifest |
| [app_settings.json](file:///d:/SC_results_WF/app_settings.json) | Runtime settings overrides (JSON) |
| [Dockerfile](file:///d:/SC_results_WF/Dockerfile) | Docker container build instructions |
| [docker-compose.yml](file:///d:/SC_results_WF/docker-compose.yml) | Multi-service orchestration: API + optional Nginx reverse proxy |
| [alembic.ini](file:///d:/SC_results_WF/alembic.ini) | Alembic database migration configuration |
| [trading_platform.log.old](file:///d:/SC_results_WF/trading_platform.log.old) | Archived execution log from a previous run |

---

## 🔧 `trading_platform/` — Core Backend

### `config.py`
Central configuration class. Key settings:
- **SierraChart paths**: `D:\SierraChart_Simulated_Feed\SavedTradeActivity` and `D:\SierraChart_Delayed_Simulated\SavedTradeActivity` — where the raw trade exports live on the developer's machine
- **API**: Host `0.0.0.0`, port `8000`, JWT auth (30-min token expiry)
- **Analysis**: 95% confidence level, 2% risk-free rate, 10,000 Monte Carlo simulations default, 252 trading days/year horizon
- **Rate limit**: 500 req/min

---

### `api/` — FastAPI Application Layer

#### [api/main.py](file:///d:/SC_results_WF/trading_platform/api/main.py)
The FastAPI app factory. Sets up:
- **CORS** (all origins, dev-mode)
- **JWT Bearer security** on all endpoints except `/health`, `/docs`, `/auth`
- **5 custom middlewares**: Logging, Error handling, Security headers, Rate limiting, Monitoring
- **20 API routers** mounted under versioned `/api/v1/` prefixes

**Full router list:**

| Router | Prefix | Purpose |
|--------|--------|---------|
| `auth` | `/api/v1/auth` | Login, token generation |
| `accounts` | `/api/v1/accounts` | Account listing & stats |
| `account_management` | `/api/v1/accounts` | Create/edit/delete accounts |
| `trades` | `/api/v1/trades` | Trade CRUD |
| `trade_import` | `/api/v1/trades` & `/api/v1/trade-import` | Paste-import from Sierra Chart |
| `analytics` | `/api/v1/analytics` | Core performance analytics (~263KB router!) |
| `time_bin_analytics` | `/api/v1/time-bins` | 30-min time-window analysis |
| `recommendations` | `/api/v1/recommendations` | Basic trading recommendations |
| `advanced_recommendations` | `/api/v1/recommendations` | ML-driven advanced recommendations |
| `data_ingestion` | `/api/v1/data` | File-based data imports |
| `exports` | `/api/v1/exports` | CSV/JSON data export |
| `backtesting` | `/api/backtesting` | Strategy backtesting runner |
| `vix_regime` | `/api/vix-regime` | VIX-based market regime analysis |
| `system` | (root) | System monitoring |
| `analysis` | (root) | Long-running analysis jobs |
| `health` | `/api/v1` | Health & monitoring metrics |

#### [api/middleware.py](file:///d:/SC_results_WF/trading_platform/api/middleware.py)
5 middleware layers (~9KB):
- **LoggingMiddleware** — request/response logging with timing
- **ErrorHandlingMiddleware** — unhandled exceptions → consistent JSON
- **SecurityHeadersMiddleware** — X-Frame-Options, CSP, etc.
- **RateLimitMiddleware** — per-IP sliding window rate limiting
- **MonitoringMiddleware** — tracks slow requests, error rates

#### [api/dependencies.py](file:///d:/SC_results_WF/trading_platform/api/dependencies.py)
FastAPI dependency injection (~11KB): database session factory, service container that lazily instantiates all major services.

#### [api/exceptions.py](file:///d:/SC_results_WF/trading_platform/api/exceptions.py)
Custom exception hierarchy with structured error types: `TradingPlatformException`, `DataNotFoundError`, `ValidationError`, `ImportError`, etc.

---

### `models/` — SQLAlchemy ORM Models

| File | Models & Purpose |
|------|-----------------|
| [database.py](file:///d:/SC_results_WF/trading_platform/models/database.py) | `ProcessedTrade` — central trade record; `Account`; `ImportSession` |
| [trading.py](file:///d:/SC_results_WF/trading_platform/models/trading.py) | Pydantic schemas: `TradingRecommendation`, `PerformanceMetrics`, `Account` |
| [sierra_chart.py](file:///d:/SC_results_WF/trading_platform/models/sierra_chart.py) | SierraChart-specific raw models |
| [sierra_chart_trades.py](file:///d:/SC_results_WF/trading_platform/models/sierra_chart_trades.py) | Trade list format models |
| [time_bin_analytics.py](file:///d:/SC_results_WF/trading_platform/models/time_bin_analytics.py) | `MarketData`, `RegimePerformance`, time-bin ORM models |

---

### `database/` — Database Infrastructure

| File | Purpose |
|------|---------|
| [connection.py](file:///d:/SC_results_WF/trading_platform/database/connection.py) | SQLAlchemy engine + `get_db_session()` context manager |
| [database.py](file:///d:/SC_results_WF/trading_platform/database/database.py) | `SessionLocal` factory, engine config |
| [base.py](file:///d:/SC_results_WF/trading_platform/database/base.py) | Declarative base for all ORM models |
| [init_db.py](file:///d:/SC_results_WF/trading_platform/database/init_db.py) | DB schema initialization (creates all tables) |
| [mcp_client.py](file:///d:/SC_results_WF/trading_platform/database/mcp_client.py) | MCP (Model Context Protocol) client for AI integration |
| [mcp_config.py](file:///d:/SC_results_WF/trading_platform/database/mcp_config.py) | MCP server configuration |
| [mcp_implementation.py](file:///d:/SC_results_WF/trading_platform/database/mcp_implementation.py) | MCP tool implementations |
| [mcp_wrapper.py](file:///d:/SC_results_WF/trading_platform/database/mcp_wrapper.py) | MCP wrapping layer for the API |
| [mcp_kiro_wrapper.py](file:///d:/SC_results_WF/trading_platform/database/mcp_kiro_wrapper.py) | Kiro-specific MCP integration |

> **Note**: The MCP files suggest this platform can expose its data as MCP tools consumable by AI agents (like Claude).

---

### `repositories/` — Data Access Layer

| File | Purpose |
|------|---------|
| [base_repository.py](file:///d:/SC_results_WF/trading_platform/repositories/base_repository.py) | Generic CRUD base with filtering, pagination |
| [trade_repository.py](file:///d:/SC_results_WF/trading_platform/repositories/trade_repository.py) | Trade queries: by account, date range, symbol |
| [account_repository.py](file:///d:/SC_results_WF/trading_platform/repositories/account_repository.py) | Account management queries |
| [metrics_repository.py](file:///d:/SC_results_WF/trading_platform/repositories/metrics_repository.py) | Pre-computed metric retrieval |
| [working_account_repository.py](file:///d:/SC_results_WF/trading_platform/repositories/working_account_repository.py) | Active/working account queries |
| [mcp_repository.py](file:///d:/SC_results_WF/trading_platform/repositories/mcp_repository.py) | MCP-specific data access |
| [working_mcp_repository.py](file:///d:/SC_results_WF/trading_platform/repositories/working_mcp_repository.py) | Working MCP data queries |

---

### `services/` — The Business Logic Engine

This is the heart of the platform. 28 files + 9 sub-packages.

#### 📥 Data Ingestion Services

| File | Size | Purpose |
|------|------|---------|
| [binary_log_parser.py](file:///d:/SC_results_WF/trading_platform/services/binary_log_parser.py) | **87KB / 1663 lines** | **The most complex file.** Parses Sierra Chart's proprietary binary `.scid` / activity log files. Handles 13 futures symbols (ES, MES, NQ, MNQ, CL, MCL, GC, SI, YM, RTY, FDAX, etc.) with price validation, timezone conversion to NY time, session boundary detection, and struct-based binary parsing. |
| [trade_import_service.py](file:///d:/SC_results_WF/trading_platform/services/trade_import_service.py) | **41KB / 906 lines** | Parses Sierra Chart's **26-column tab-delimited TradesList.txt** paste format. Handles full trade lifecycle: entry/exit prices, commissions, PnL, flat-to-flat stats, efficiency metrics, duplicate detection, and upsert logic. |
| [sierra_chart_parser.py](file:///d:/SC_results_WF/trading_platform/services/sierra_chart_parser.py) | 17KB | Sierra Chart text file format parser |
| [processed_trade_parser.py](file:///d:/SC_results_WF/trading_platform/services/processed_trade_parser.py) | 14KB | Parses already-processed trade files |
| [processed_trade_service.py](file:///d:/SC_results_WF/trading_platform/services/processed_trade_service.py) | 25KB | Business logic for processed trades |
| [data_ingestion_service.py](file:///d:/SC_results_WF/trading_platform/services/data_ingestion_service.py) | 20KB | Orchestrates multi-source data ingestion |
| [import_rollback_service.py](file:///d:/SC_results_WF/trading_platform/services/import_rollback_service.py) | 15KB | Rolls back failed imports safely |
| [import_validation_service.py](file:///d:/SC_results_WF/trading_platform/services/import_validation_service.py) | 26KB | Pre-import data validation and sanity checks |
| [trade_completion_service.py](file:///d:/SC_results_WF/trading_platform/services/trade_completion_service.py) | 18KB | Handles incomplete/partial trade records |
| [enhanced_fill_matcher.py](file:///d:/SC_results_WF/trading_platform/services/enhanced_fill_matcher.py) | 16KB | Matches raw order fills to completed round-trip trades |

#### 📊 Analytics Services

| File | Size | Purpose |
|------|------|---------|
| [time_bin_analyzer.py](file:///d:/SC_results_WF/trading_platform/services/time_bin_analyzer.py) | **22KB / 567 lines** | **Core analytics engine.** Divides the trading day into 30-minute bins and computes per-account performance in each bin. Uses statistical significance testing (t-tests, bootstrapping) to identify genuinely profitable time windows. |
| [temporal_analysis_service.py](file:///d:/SC_results_WF/trading_platform/services/temporal_analysis_service.py) | 21KB | Day-of-week, month, session-hour pattern analysis |
| [performance_metrics_calculator.py](file:///d:/SC_results_WF/trading_platform/services/performance_metrics_calculator.py) | 17KB | Calculates Sharpe, Sortino, Calmar, win rate, profit factor, max drawdown, etc. |
| [benchmark_comparison_analyzer.py](file:///d:/SC_results_WF/trading_platform/services/benchmark_comparison_analyzer.py) | 29KB | Compares account performance against benchmarks |
| [account_comparison_service.py](file:///d:/SC_results_WF/trading_platform/services/account_comparison_service.py) | 28KB | Side-by-side account performance comparison |
| [account_validation_service.py](file:///d:/SC_results_WF/trading_platform/services/account_validation_service.py) | 21KB | Validates account data integrity |
| [data_validation_service.py](file:///d:/SC_results_WF/trading_platform/services/data_validation_service.py) | 22KB | General data quality validation |
| [statistical_testing_engine.py](file:///d:/SC_results_WF/trading_platform/services/statistical_testing_engine.py) | 10KB | Bootstrap tests, t-tests, significance thresholds |
| [sample_data_validator.py](file:///d:/SC_results_WF/trading_platform/services/sample_data_validator.py) | 14KB | Validates sample datasets against expected schema |

#### 📈 Market Data Services

| File | Size | Purpose |
|------|------|---------|
| [market_data_ingestion.py](file:///d:/SC_results_WF/trading_platform/services/market_data_ingestion.py) | 26KB | Pulls VIX and other market data from external sources |
| [multi_source_market_data.py](file:///d:/SC_results_WF/trading_platform/services/multi_source_market_data.py) | 19KB | Aggregates data from multiple market data providers |
| [free_market_data.py](file:///d:/SC_results_WF/trading_platform/services/free_market_data.py) | 13KB | Free-tier market data fetching (yfinance etc.) |
| [market_data_service.py](file:///d:/SC_results_WF/trading_platform/services/market_data_service.py) | 3KB | Market data service facade |
| [market_data_types.py](file:///d:/SC_results_WF/trading_platform/services/market_data_types.py) | 1KB | Market data type definitions |
| [vix_regime_analyzer.py](file:///d:/SC_results_WF/trading_platform/services/vix_regime_analyzer.py) | **29KB / 680 lines** | **VIX regime classification.** Labels each trading day as Low (VIX<15), Medium (VIX 15-25), or High (VIX>25) volatility regime. Aligns trades to their regime for conditional analytics — *"does this strategy work in high-VIX environments?"* |

---

### `services/machine_learning/` — ML Prediction Engine

| File | Size | Purpose |
|------|------|---------|
| [feature_engineer.py](file:///d:/SC_results_WF/trading_platform/services/machine_learning/feature_engineer.py) | 22KB | Transforms raw trades into ML features (time-of-day, day-of-week, rolling stats, VIX regime, etc.) |
| [model_trainer.py](file:///d:/SC_results_WF/trading_platform/services/machine_learning/model_trainer.py) | 37KB | Trains multiple sklearn models: Random Forest, Gradient Boosting, XGBoost, Linear models |
| [prediction_service.py](file:///d:/SC_results_WF/trading_platform/services/machine_learning/prediction_service.py) | **46KB / 1138 lines** | **Ensemble prediction engine.** Combines multiple trained models via `VotingRegressor`/`VotingClassifier`. Generates predictions with confidence intervals, supports A/B model comparison, caches predictions, and runs predictions in parallel threads. |
| [feature_importance_analyzer.py](file:///d:/SC_results_WF/trading_platform/services/machine_learning/feature_importance_analyzer.py) | 20KB | SHAP-style feature importance analysis — which features drive the model's predictions |

---

### `services/monte_carlo/` — Risk Simulation Engine

| File | Size | Purpose |
|------|------|---------|
| [monte_carlo_simulator.py](file:///d:/SC_results_WF/trading_platform/services/monte_carlo/monte_carlo_simulator.py) | 17KB | Basic Monte Carlo simulator for single accounts |
| [parallel_monte_carlo_engine.py](file:///d:/SC_results_WF/trading_platform/services/monte_carlo/parallel_monte_carlo_engine.py) | **28KB** | **High-performance parallel engine** using `joblib`. Supports 4 simulation types: Bootstrap, Parametric, Regime-Conditional, and Comprehensive. Has progress tracking, job cancellation, UUID-based simulation IDs. |
| [parallel_monte_carlo_processor.py](file:///d:/SC_results_WF/trading_platform/services/monte_carlo/parallel_monte_carlo_processor.py) | 38KB | Distributes Monte Carlo work across CPU cores |
| [scenario_generator.py](file:///d:/SC_results_WF/trading_platform/services/monte_carlo/scenario_generator.py) | 16KB | Generates random trade sequence scenarios |
| [time_bin_scenario_generator.py](file:///d:/SC_results_WF/trading_platform/services/monte_carlo/time_bin_scenario_generator.py) | **36KB** | Generates scenarios conditioned on time-bin and VIX regime — most sophisticated simulation module |
| [risk_calculator.py](file:///d:/SC_results_WF/trading_platform/services/monte_carlo/risk_calculator.py) | 20KB | Computes VaR (Value at Risk), CVaR/ES (Expected Shortfall) |
| [risk_metrics_calculator.py](file:///d:/SC_results_WF/trading_platform/services/monte_carlo/risk_metrics_calculator.py) | **34KB** | Comprehensive risk report: drawdown distributions, tail risk, ruin probability |

---

### `services/recommendation/` — Trading Recommendation Engine

| File | Size | Purpose |
|------|------|---------|
| [recommendation_service.py](file:///d:/SC_results_WF/trading_platform/services/recommendation/recommendation_service.py) | 31KB | Generates trade recommendations from analytics results |
| [strategy_evaluator.py](file:///d:/SC_results_WF/trading_platform/services/recommendation/strategy_evaluator.py) | 23KB | Evaluates strategy quality and persistence |
| [backtesting_service.py](file:///d:/SC_results_WF/trading_platform/services/recommendation/backtesting_service.py) | **55KB** | Full backtesting runner — replays historical trades under strategy rules |
| [risk_optimizer.py](file:///d:/SC_results_WF/trading_platform/services/recommendation/risk_optimizer.py) | **90KB / 1898 lines** | **Largest file.** Multi-method portfolio optimizer: Mean-Variance, Sharpe Ratio, Kelly Criterion, Risk Parity, Maximum Diversification. Uses `scipy.optimize` to find optimal position sizes across accounts/symbols. |

---

### `services/walk_forward/` — Strategy Robustness Validation

| File | Size | Purpose |
|------|------|---------|
| [out_of_sample_validator.py](file:///d:/SC_results_WF/trading_platform/services/walk_forward/out_of_sample_validator.py) | **48KB / 1025 lines** | **Walk-forward analysis engine.** Tests strategies on out-of-sample data using 4 methods: Anchored Walk-Forward, Rolling Window, Expanding Window, Time-Series CV. Measures overfitting by comparing in-sample vs. out-of-sample performance. |
| [performance_decay_tracker.py](file:///d:/SC_results_WF/trading_platform/services/walk_forward/performance_decay_tracker.py) | **75KB** | Tracks how strategy performance degrades over time — identifies strategies losing their edge |

### `services/backtesting/` — Backtesting Engine

| File | Size | Purpose |
|------|------|---------|
| [time_bin_backtesting_engine.py](file:///d:/SC_results_WF/trading_platform/services/backtesting/time_bin_backtesting_engine.py) | 46KB | Backtests time-bin strategies on historical data |
| [backtest_results_analyzer.py](file:///d:/SC_results_WF/trading_platform/services/backtesting/backtest_results_analyzer.py) | **69KB** | Analyzes and scores backtest results |

---

### Other Service Sub-packages

| Package | Purpose |
|---------|---------|
| `services/caching/` | Response caching layer (reduces redundant computation) |
| `services/monitoring/` | Real-time performance monitoring |
| `services/export_reporting/` | CSV/JSON/Excel export logic |
| `services/database/` | Database-level service utilities |

---

## 🖥️ `frontend/` — React Dashboard

**Stack**: React 18 + TypeScript + Redux Toolkit + Plotly.js + React Router v6

Runs on port **3001**, proxies API calls to `localhost:8000`.

### Pages (9 full page-level views)

| Page | Purpose |
|------|---------|
| `Dashboard/` | Main overview: PnL summary, active accounts, quick metrics |
| `Analytics/` | Detailed trade analytics with charts |
| `Accounts/` | Account list and comparison |
| `AccountsByHour/` | Per-account performance broken down by hour of day |
| `AccountManagement/` | Create/manage trading accounts |
| `Recommendations/` | View ML-generated recommendations |
| `TradeImport/` | Paste Sierra Chart data to import trades |
| `Discovery/` | Discover top-performing time windows and strategies |
| `Monitoring/` | Real-time monitoring of system and trade data |

### Components (17 reusable components)

| Component | Purpose |
|-----------|---------|
| `MonteCarloChart/` | Visualizes Monte Carlo simulation fan charts |
| `WalkForwardResultsChart/` | Walk-forward validation result visualization |
| `VIXRegimeAnalyzer/` | VIX regime overlay on performance data |
| `TimeBinPerformanceChart/` | Heatmap of 30-min bin performance |
| `TemporalChart/` | Time-based performance charts |
| `PerformanceMetrics/` | KPI cards (Sharpe, win rate, etc.) |
| `PerformanceBreakdown/` | Drill-down performance breakdown |
| `RecommendationCard/` | Individual recommendation display card |
| `MarketCorrelationDashboard/` | Correlation matrix between instruments |
| `StrategyValidationAnalytics/` | OOS vs. IS validation result display |
| `TradingReadinessAssessment/` | Pre-trade checklist/readiness score |
| `AlertsMonitoring/` | Live alerts and threshold notifications |
| `DragDropDashboard/` | Customizable drag-and-drop widget layout |
| `InteractiveChart/` | Base interactive chart wrapper |
| `MetricCard/` | Single KPI metric display |
| `Layout/` | App shell: sidebar, header, navigation |
| `ErrorBoundary/` | React error boundary wrapper |

---

## 🔬 `scripts/` — 54 Operational Scripts

Scripts for day-to-day maintenance and operations. Key ones:

| Script | Purpose |
|--------|---------|
| `start_trading_platform.bat` | **Main launcher** — starts backend + frontend together |
| `start_backend_only.bat` | Backend-only startup |
| `start_frontend_only.bat` | Frontend-only startup |
| `restart_api.bat` | Fast API restart |
| `kill_trading_platform.bat` | Force-kill all processes |
| `run_full_import.py` | Triggers a full data import cycle |
| `reimport_from_txt.py` | Re-imports from Sierra Chart .txt exports |
| `deduplicate_db.py` | Removes duplicate trade records |
| `optimize_database.py` | VACUUM, ANALYZE, index rebuild |
| `clean_all_trades.py` | Nukes all trade records (dev/reset) |
| `compare_strategies_oos.py` | Compare strategies on out-of-sample data |
| `stationarity_test.py` | ADF/KPSS stationarity tests on trade series |
| `global_persistence_test.py` | Tests whether edges persist across time |
| `generate_dev_token.py` | Generates a dev JWT token for API testing |
| `batch_verify_range.py` | Verifies data integrity over date ranges |
| `populate_temporal_performance.py` | Pre-computes temporal analytics into DB |

---

## 🧪 Root-Level Diagnostic Scripts (72 files)

These are standalone one-off investigative scripts written during development. Organized into categories:

### `check_*` files (~20 files)
Diagnostic queries against the database or API to verify data correctness:
- `check_2024_active_accounts.py` — confirms 2024 accounts are in DB
- `check_api_accounts.py` — verifies API returns correct accounts
- `check_import_errors.py` — surfaces import failures
- `check_vsim16_api.py` — checks vSim16 account data via API
- `check_all_jan_mar.py` — verifies Jan–Mar data completeness

### `find_*` files (~8 files)
Searches for specific data patterns:
- `find_2024_vsim16.py` — finds all vSim16 account trades in 2024
- `find_continuous_accounts.py` — identifies accounts with continuous trading history
- `find_outliers.py` — statistical outlier detection

### `verify_*` files
Data integrity verification:
- `verify_db.py` — full DB integrity check
- `verify_cache.py` — cache consistency check
- `verify_jan_mar.py` — Jan-March data range verification

### `import_historical_vsim16*.py`
Scripts to batch-import historical vSim16 permutation data.

### `integrate_advanced_recommendations.py`
A 25KB script that integrates the advanced ML recommendation system — acts as a deployment/wiring script.

---

## 📚 `docs/` — 25 Documentation Files

Rich operational documentation:

| Document | Content |
|----------|---------|
| [STARTUP_GUIDE.md](file:///d:/SC_results_WF/docs/STARTUP_GUIDE.md) | Step-by-step platform startup instructions |
| [IMPORT_SHIELD_CORE_RULES.md](file:///d:/SC_results_WF/docs/IMPORT_SHIELD_CORE_RULES.md) | Rules that prevent bad data from entering the DB |
| [ghost_trade_identification.md](file:///d:/SC_results_WF/docs/ghost_trade_identification.md) | How to detect and handle "ghost" trades (Sierra Chart artifacts) |
| [live_trading_playbook.md](file:///d:/SC_results_WF/docs/live_trading_playbook.md) | Practical playbook for live trading decisions |
| [SC_TAL_REVERSE_ENGINEERING.md](file:///d:/SC_results_WF/docs/SC_TAL_REVERSE_ENGINEERING.md) | Documentation of reverse-engineering Sierra Chart's Trade Activity Log binary format |
| [session_hours_and_timezone.md](file:///d:/SC_results_WF/docs/session_hours_and_timezone.md) | Session hours, timezone handling (NY time focus) |
| [trade_import_logic_and_validation.md](file:///d:/SC_results_WF/docs/trade_import_logic_and_validation.md) | Full import pipeline documentation |
| [ADVANCED_ANALYTICS_INTEGRATION_SUMMARY.md](file:///d:/SC_results_WF/docs/ADVANCED_ANALYTICS_INTEGRATION_SUMMARY.md) | Summary of ML/analytics integration |
| [TESTING_GUIDE.md](file:///d:/SC_results_WF/docs/TESTING_GUIDE.md) | Test suite documentation |
| [UNIFIED_DISCOVERY_HUB.md](file:///d:/SC_results_WF/docs/UNIFIED_DISCOVERY_HUB.md) | Discovery hub feature documentation |

---

## 🗄️ Database Schema (Key Tables)

Based on the models and services:

- **`processed_trades`** — central table: all normalized trades with entry/exit price, PnL, commission, account_name, symbol, timestamps
- **`accounts`** — trading accounts (e.g., "vSim16", "SIM-15")
- **`import_sessions`** — audit log of every import run
- **`market_data`** — VIX and other market data series
- **`regime_performance`** — pre-computed performance per VIX regime
- **`time_bin_metrics`** — pre-computed per-bin analytics

**Database**: SQLite (`trading_platform.db`) managed via SQLAlchemy ORM with Alembic migrations.

---

## 🔑 Key Instruments & Accounts

From the code, the platform tracks these **futures instruments**:

| Symbol | Full Name | Contract Multiplier |
|--------|-----------|-------------------|
| ES | E-mini S&P 500 | $50/pt |
| MES | Micro E-mini S&P 500 | $5/pt |
| NQ | E-mini NASDAQ-100 | $20/pt |
| MNQ | Micro E-mini NASDAQ | $2/pt |
| CL | Crude Oil | $1000/pt |
| MCL | Micro Crude Oil | $100/pt |
| GC | Gold | $100/oz |
| SI | Silver | $5000/contract |
| YM | Dow Jones E-mini | $5/pt |
| MYM | Micro Dow Jones | $0.50/pt |
| RTY | Russell 2000 E-mini | $50/pt |
| M2K | Micro Russell 2000 | $5/pt |
| FDAX | DAX Futures | €25/pt |

**Account types** referenced: `vSim16`, `SIM-15`, `SIM-14`, `SIM-13`, `ts4`, `CL` — these are Sierra Chart simulated permutation accounts used for strategy comparison.

---

## 🧬 What Makes This Platform Special

### 1. **Sierra Chart Binary Parser**
The `binary_log_parser.py` (87KB!) reverse-engineers Sierra Chart's proprietary binary `.scid` trade activity log format using Python's `struct` module. This is non-trivial work — it was documented in `SC_TAL_REVERSE_ENGINEERING.md`.

### 2. **Time-Bin Edge Discovery**
The core insight of the platform: *not all hours of the trading day are equally profitable*. The time-bin analyzer finds which 30-minute windows statistically outperform, using bootstrap significance testing to avoid false positives.

### 3. **Regime-Conditional Analytics**
Every analysis is segmented by VIX regime (Low/Medium/High volatility). A strategy that works in calm markets may fail in volatile ones — this platform finds out.

### 4. **Walk-Forward Validation**
The platform actively guards against overfitting using out-of-sample validation, tracking whether historical edges persist in new data ("performance decay tracking").

### 5. **Parallel Monte Carlo**
10,000+ simulations run in parallel via `joblib` across CPU cores — for large-scale risk assessment in reasonable time.

### 6. **Multi-Method Portfolio Optimization**
5 optimization algorithms (Mean-Variance, Sharpe, Kelly, Risk Parity, Max Diversification) to allocate capital across accounts/instruments.

---

## 🚀 How to Run

### Development Mode
```bash
# Backend (from root)
python main.py

# Frontend (from frontend/)
npm start   # Runs on port 3001
```

### Via Scripts
```bat
scripts\start_trading_platform.bat    # starts both
scripts\restart_api.bat               # restart API only
```

### Docker
```bash
docker-compose up
```

### API Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health: `http://localhost:8000/health`

---

## 📊 Scale & Complexity Numbers

| Metric | Value |
|--------|-------|
| Total root files | 72 files + 18 directories |
| Backend Python files | ~80+ files |
| Frontend TypeScript files | ~50+ files |
| Largest single file | `risk_optimizer.py` — 90KB, 1898 lines |
| Most complex parser | `binary_log_parser.py` — 87KB, 1663 lines |
| Largest router | `analytics.py` — 263KB |
| API endpoints | ~100+ across 20 routers |
| Monte Carlo default simulations | 10,000 per run |
| Supported futures instruments | 13 |
| Documentation files | 25 in `/docs` |
| Operational scripts | 54 in `/scripts` |

---

## 🧭 Summary

This is a **professional-grade algorithmic trading research platform** built by an active futures trader to:

1. **Import** trade data from Sierra Chart (both text paste and binary log file formats)
2. **Store** it in a normalized SQLite database
3. **Analyze** it across time-of-day, day-of-week, VIX regime, and account dimensions
4. **Validate** strategy edges with walk-forward out-of-sample testing
5. **Simulate** portfolio risk with parallel Monte Carlo
6. **Optimize** position sizing with multi-method portfolio optimization
7. **Predict** future performance using ensemble ML models
8. **Recommend** which accounts and time windows to focus on
9. **Visualize** everything in a React dashboard with Plotly charts
