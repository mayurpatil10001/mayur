# Sierra Chart Trade Optimization Platform — Architectural Blueprint

> **Classification**: Principal Architect Review Document
> **Based on**: Live audit of `github.com/mayurpatil10001/mayur` (commit `f09826f3`)
> **Date**: July 26, 2026
> **Status**: Design Approved — Pending Phase 1 Execution

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Canonical Monorepo Structure](#2-canonical-monorepo-structure)
3. [Deletion Manifest — 80+ Throwaway Scripts](#3-deletion-manifest--80-throwaway-scripts)
4. [Backend Architecture (`/backend/`)](#4-backend-architecture-backend)
5. [Database Layer and Migration Path](#5-database-layer-and-migration-path)
6. [API Design — Versioned Routes](#6-api-design--versioned-routes)
7. [Frontend Architecture (`/frontend/`)](#7-frontend-architecture-frontend)
8. [Data Flow Pipeline (End-to-End)](#8-data-flow-pipeline-end-to-end)
9. [Five-Phase Development Roadmap](#9-five-phase-development-roadmap)
10. [Security and Configuration Design](#10-security-and-configuration-design)
11. [Technology Decisions](#11-technology-decisions)
12. [Makefile Task Runner](#12-makefile-task-runner)

---

## 1. Current State Assessment

### What Exists (From Live Audit)

The repository has grown organically without enforced structure. The result is a partially-layered codebase with significant technical debt at the root level.

**Root-Level Chaos** (Items that should NOT be at root):
```
main.py                                    <- app entry point at root (wrong)
alembic.ini                                <- migration config at root (wrong)
alembic/                                   <- migration scripts at root (wrong)
models/                                    <- duplicate of trading_platform/models/ (wrong)
scratch_parser_test.db                     <- test artifact committed (wrong)
trading_platform.db                        <- production database at root (wrong)
trading_platform.log / .log.old            <- log files committed (wrong)
ghost_all.log                              <- debug log committed (wrong)
import_debug.log / import_files_trace.log  <- debug logs committed (wrong)
ghost_fill_audit.md                        <- audit doc at root (wrong)
project_deep_dive.md                       <- doc at root (wrong)
New folder/                                <- unnamed development artifact
3/                                         <- unnamed folder
rar_extract/                               <- extraction artifact
.bmad-core/ .claude/ .cursor/ .kiro/ .qodo <- IDE configs (gitignore only)
5x PDF audit files                         <- binary docs at root (wrong)
```

**What Is Partially Correct**:
- `trading_platform/` has real layering: `api/`, `services/`, `models/`, `repositories/`, `interfaces/`, `utils/`
- `frontend/` has pages, components, store slices, and a services layer
- `.github/`, `.env.example`, `docker-compose.yml`, `Dockerfile` exist
- `tests/`, `docs/`, `scripts/`, `data/` folders exist but are inconsistently used

**What Is Broken**:
- `scripts/` contains 80+ files mixing production ops, one-off debugs, and throwaway checks
- `legacy/`, `scratch/`, `debug/` folders contain dead code with no archival policy
- `trading_platform/services/` is overloaded: it hosts 30+ flat files plus 8 subpackages
- No clear boundary between public API contracts and internal service logic
- `models/` exists both at root AND inside `trading_platform/` (duplication)
- Alembic not wired to `trading_platform/` models — migrations are manual
- No consistent service interface pattern (some services use ABC, most do not)
- Frontend `SortinoLeaderboard.tsx` lives flat in `components/` while all others are in subfolders

### Severity Classification

| Issue | Severity | Impact |
| :--- | :--- | :--- |
| 80+ throwaway scripts in `scripts/` | CRITICAL | New contributors cannot identify operational scripts |
| `trading_platform.db` at root | CRITICAL | Production data in VCS scope |
| Duplicate `models/` at root | HIGH | Import confusion, stale schemas |
| No Alembic-to-models wiring | HIGH | Migrations drift from ORM |
| `legacy/`, `scratch/`, `debug/` | HIGH | Dead code increases cognitive load |
| Flat `services/` with 30+ files | MEDIUM | Hard to navigate, no boundary enforcement |
| Log files committed | MEDIUM | Repository bloat |
| No API versioning | MEDIUM | Breaking changes affect all consumers |
| No service interface contracts | MEDIUM | Services tightly coupled to callers |

---

## 2. Canonical Monorepo Structure

### Target Structure

```
SC_results_WF/                             <- Repository root
|
|-- backend/                               <- All Python server code (rename from trading_platform/)
|   |-- alembic/                           <- Database migrations (moved from root)
|   |   |-- versions/
|   |   |-- env.py
|   |   |-- script.py.mako
|   |-- api/
|   |   |-- __init__.py
|   |   |-- app.py                         <- FastAPI app factory (moved from root main.py)
|   |   |-- dependencies.py               <- Shared FastAPI dependencies (DB session, auth)
|   |   |-- middleware.py                  <- CORS, logging, timing middleware
|   |   |-- v1/                            <- Versioned API namespace
|   |   |   |-- __init__.py
|   |   |   |-- router.py                  <- Aggregates all v1 routers
|   |   |   |-- routes/
|   |   |   |   |-- trades.py
|   |   |   |   |-- analytics.py
|   |   |   |   |-- accounts.py
|   |   |   |   |-- walkforward.py
|   |   |   |   |-- recommendations.py
|   |   |   |   |-- import_jobs.py
|   |-- core/
|   |   |-- config.py                      <- Pydantic Settings (reads .env)
|   |   |-- logging.py                     <- Structured logging setup
|   |   |-- security.py                    <- API key validation, JWT helpers
|   |   |-- exceptions.py                  <- Custom HTTPExceptions
|   |-- db/
|   |   |-- base.py                        <- SQLAlchemy declarative base
|   |   |-- session.py                     <- Engine + SessionLocal factory
|   |   |-- init_db.py                     <- Schema creation, seed data
|   |   |-- connection_pool.py             <- Pool config (moved from services/database/)
|   |-- models/                            <- SQLAlchemy ORM models (single source of truth)
|   |   |-- __init__.py
|   |   |-- trade.py                       <- ProcessedTrade, PendingFill
|   |   |-- account.py                     <- Account, AccountConfig
|   |   |-- analytics.py                   <- TimeBinMetrics, PerformanceSnapshot
|   |   |-- import_job.py                  <- ImportJob, ImportJobStatus
|   |-- schemas/                           <- Pydantic request/response schemas
|   |   |-- __init__.py
|   |   |-- trade.py
|   |   |-- analytics.py
|   |   |-- account.py
|   |   |-- walkforward.py
|   |   |-- recommendation.py
|   |   |-- import_job.py
|   |-- repositories/                      <- Data access layer (keep, clean up)
|   |   |-- __init__.py
|   |   |-- base.py                        <- BaseRepository[T]
|   |   |-- trade_repository.py
|   |   |-- account_repository.py
|   |   |-- metrics_repository.py
|   |-- services/                          <- Business logic (reorganize into subpackages)
|   |   |-- __init__.py
|   |   |-- ingestion/                     <- Binary log parsing pipeline
|   |   |   |-- binary_log_parser.py       <- GFRE core (production parser)
|   |   |   |-- ghost_fill_filter.py       <- Extracted ghost detection logic
|   |   |   |-- fill_pairer.py             <- FIFO pairing logic
|   |   |   |-- deduplicator.py            <- Per-file + global dedup
|   |   |   |-- import_orchestrator.py     <- Coordinates full import pipeline
|   |   |-- analytics/                     <- Performance analytics
|   |   |   |-- performance_calculator.py
|   |   |   |-- time_bin_analyzer.py
|   |   |   |-- temporal_analysis.py
|   |   |   |-- benchmark_comparator.py
|   |   |-- walkforward/                   <- Walk-forward testing
|   |   |   |-- walk_forward_engine.py
|   |   |   |-- out_of_sample_validator.py
|   |   |   |-- performance_decay_tracker.py
|   |   |-- montecarlo/                    <- Monte Carlo simulation
|   |   |   |-- simulator.py
|   |   |   |-- parallel_engine.py
|   |   |   |-- scenario_generator.py
|   |   |   |-- risk_calculator.py
|   |   |-- recommendation/               <- Strategy recommendations
|   |   |   |-- recommendation_engine.py
|   |   |   |-- strategy_evaluator.py
|   |   |   |-- risk_optimizer.py
|   |   |   |-- backtesting_service.py
|   |   |-- statistical/                   <- Statistical testing (BH-FDR, permutation)
|   |   |   |-- testing_engine.py
|   |   |   |-- bh_fdr_gate.py
|   |   |   |-- permutation_test.py
|   |   |   |-- stationarity.py
|   |   |-- market_data/                   <- External market data
|   |   |   |-- market_data_service.py
|   |   |   |-- vix_regime_analyzer.py
|   |   |   |-- free_market_data.py
|   |   |-- ml/                            <- Machine learning models
|   |   |   |-- feature_engineer.py
|   |   |   |-- model_trainer.py
|   |   |   |-- prediction_service.py
|   |   |-- export/                        <- Report generation
|   |   |   |-- pdf_generator.py
|   |   |   |-- data_exporter.py
|   |   |-- monitoring/                    <- Alerts and health
|   |   |   |-- alert_manager.py
|   |   |   |-- health_monitor.py
|   |   |   |-- metrics_collector.py
|   |-- utils/                             <- Pure utility functions (keep)
|   |   |-- logging.py
|   |   |-- timezone_utils.py
|   |   |-- validators.py
|   |-- main.py                            <- Uvicorn entrypoint (import from api/app.py)
|   |-- requirements.txt                   <- Moved from root
|   |-- alembic.ini                        <- Moved from root
|
|-- frontend/                              <- React 18 + TypeScript (keep, clean internals)
|   |-- src/
|   |   |-- app/
|   |   |   |-- App.tsx
|   |   |   |-- router.tsx                 <- React Router config
|   |   |-- features/                      <- Feature modules (replaces flat pages/)
|   |   |   |-- dashboard/
|   |   |   |-- analytics/
|   |   |   |-- accounts/
|   |   |   |-- walkforward/
|   |   |   |-- recommendations/
|   |   |   |-- import/
|   |   |   |-- monitoring/
|   |   |-- shared/                        <- Shared components (replaces flat components/)
|   |   |   |-- charts/
|   |   |   |-- ui/
|   |   |   |-- layout/
|   |   |-- store/                         <- Redux Toolkit (keep, expand)
|   |   |-- services/                      <- API client layer (keep)
|   |   |-- types/                         <- Shared TypeScript types (keep)
|   |-- package.json
|   |-- tsconfig.json
|   |-- vite.config.ts
|
|-- scripts/                               <- OPERATIONAL SCRIPTS ONLY (10 max)
|   |-- promote.py                         <- Promote clean data to production view
|   |-- run_import.py                      <- Trigger full binary log import
|   |-- run_walk_forward.py                <- Run WF test suite
|   |-- run_permutation_test.py            <- Run BH-FDR permutation gate
|   |-- run_out_of_sample.py               <- OOS validation
|   |-- migrate_db.py                      <- Run Alembic migrations
|   |-- generate_report.py                 <- Generate PDF audit reports
|   |-- start.bat / start.sh               <- Cross-platform start scripts
|
|-- tests/                                 <- Consolidated pytest suite
|   |-- conftest.py                        <- Shared fixtures, test DB setup
|   |-- unit/
|   |   |-- test_ghost_fill_filter.py
|   |   |-- test_fill_pairer.py
|   |   |-- test_performance_calculator.py
|   |   |-- test_bh_fdr_gate.py
|   |   |-- test_walk_forward_engine.py
|   |-- integration/
|   |   |-- test_import_pipeline.py
|   |   |-- test_api_trades.py
|   |   |-- test_api_analytics.py
|   |-- fixtures/
|   |   |-- sample_binary_log.data         <- Minimal 10-fill binary fixture
|   |   |-- expected_trades.json
|
|-- data/                                  <- Sample data only (never production data)
|   |-- samples/
|   |   |-- sample_log_10fills.data
|   |   |-- sample_graphdata.txt
|   |-- README.md                          <- Explains dataset/ is gitignored
|
|-- docs/                                  <- All documentation (migrate root .md files here)
|   |-- ARCHITECTURE_BLUEPRINT.md          <- THIS FILE
|   |-- PROJECT_OVERVIEW.md                <- Moved from root
|   |-- ghost_fill_audit.md                <- Moved from root
|   |-- reports/                           <- PDF audit reports (moved from root)
|   |   |-- MASTER_PROJECT_UPDATES_AUDIT.pdf
|   |   |-- WALK_FORWARD_TEST_AUDIT.pdf
|   |   |-- FULL_562_DAY_STAGE4_PIPELINE_AUDIT.pdf
|
|-- infra/                                 <- All infrastructure config
|   |-- docker/
|   |   |-- Dockerfile.backend
|   |   |-- Dockerfile.frontend
|   |   |-- nginx.conf
|   |-- docker-compose.yml                 <- Moved from root
|   |-- docker-compose.prod.yml
|   |-- .github/                           <- Moved from root
|   |   |-- workflows/
|   |   |   |-- ci.yml
|   |   |   |-- deploy.yml
|
|-- PROJECT_OVERVIEW.md                    <- KEEP at root (entry point for AI/reviewers)
|-- README.md                              <- Keep at root
|-- Makefile                               <- Unified task runner (new)
|-- .env                                   <- Local secrets (gitignored)
|-- .env.example                           <- Committed template
|-- .gitignore                             <- Update to cover new paths
|-- LICENSE
|-- CONTRIBUTING.md
```

---

## 3. Deletion Manifest — 80+ Throwaway Scripts

### Decision Framework

A script is **deletable** if it matches ANY of:
- Name contains: `check_`, `find_`, `detect_`, `debug_`, `compare_`, `nuke_`, `wipe_`, `clear_`, `nuclear_`, `_test.py` (one-off), `thorough_`, `simple_`, `global_`
- File was created for a single-session investigation and has no import dependents
- Logic is now superseded by a service class in `trading_platform/services/`
- File produces output that is already captured in `docs/*.csv` or `docs/*.pdf`

### Delete (Move to Archive Branch First, Then Delete)

| File | Reason |
| :--- | :--- |
| `_audit_credentials.py` | One-off credential check; no production value |
| `_audit_date_coverage.py` | One-off date gap finder; superseded by import pipeline |
| `_debug_time_bin.py` | Debug session artifact |
| `analyze_account.py` | Ad-hoc; superseded by `/api/v1/analytics` |
| `analyze_qty_breakdown.py` | Ad-hoc quantity inspector; no ongoing value |
| `analyze_spikes.py` | One-off PnL spike finder |
| `audit_ghost_fills.py` | Superseded by GFRE in `binary_log_parser.py` |
| `batch_verify_range.py` | One-off verification; superseded by `run_out_of_sample.py` |
| `calc_bad_pnl.py` | One-off calculation; superseded by performance calculator |
| `check_open_position_bounds.py` | Debug check; superseded by GFRE integrity verifier |
| `clean_all_trades.py` | Dangerous: deletes DB rows; use migration instead |
| `clean_binary_garbage.py` | One-off cleanup; GFRE now prevents bad data |
| `clean_garbage.py` | Duplicate of above |
| `clean_ts4_reimport.py` | Account-specific one-off |
| `clear_db.py` | Dangerous: nukes DB; use `migrate_db.py --reset` instead |
| `clear_sim14.py` | Account-specific one-off |
| `clear_sim15.py` | Account-specific one-off |
| `compare_clean_pipeline_session_pnl.py` | Session comparison; results in audit PDFs |
| `compare_day.py` | Ad-hoc day comparator |
| `compare_pipeline_session_pnl.py` | Duplicate comparison script |
| `compare_recommendation_ab.py` | A/B results captured in audit PDF |
| `compare_sc_txt.py` | SC txt vs binary compare; superseded by `full_signal_fill_sync.py` |
| `compare_strategies_oos.py` | OOS comparison; superseded by `run_out_of_sample.py` |
| `compare_verification_vs_processed.py` | Verification artifact |
| `comprehensive_processed_import.py` | Superseded by production import pipeline |
| `convert_md_to_pdf.py` | Utility; belongs in `Makefile` as a target |
| `correlate_qty.py` | Ad-hoc quantity correlation |
| `db_cleanup_outliers.py` | Dangerous; outlier logic belongs in import pipeline |
| `debug_pnl_jump.py` | Debug artifact |
| `deduplicate_db.py` | Superseded by GFRE deduplication stage |
| `final_nuke.py` | Destructive; no production use |
| `find_duplicates.py` | Superseded by GFRE global dedup |
| `force_import_sim15_gap.py` | Account-specific one-off |
| `generate_500_day_audit_report.py` | Result in docs/; no longer needs regenerating |
| `generate_dev_token.py` | Move to `backend/core/security.py` as a function |
| `generate_detailed_session_ab_audit.py` | Results captured; archive |
| `generate_full_562_day_stage4_audit.py` | Results captured; archive |
| `generate_master_project_update_audit.py` | Results captured; archive |
| `generate_pipeline_superiority_audit.py` | Results captured; archive |
| `generate_ultra_detailed_master_audit.py` | Results captured; archive |
| `global_persistence_test.py` | One-off persistence test |
| `inspect_10_sequences.py` | Ad-hoc sequence inspector |
| `inspect_problematic_sequences.py` | Superseded by `tm7_nq_ghost_analysis.py` |
| `integrate_advanced_recommendations.py` | One-off integration script |
| `nuclear_clear_ts4.py` | Dangerous; account-specific |
| `nuke_garbage.py` | Dangerous; vague; delete |
| `optimize_database.py` | Superseded by `services/database/query_optimizer.py` |
| `optimize_oos_selection.py` | OOS logic belongs in `walkforward/` service |
| `populate_temporal_performance.py` | One-off population; belongs in import pipeline |
| `reimport_from_txt.py` | One-off |
| `reimport_sim13.py` | Account-specific one-off |
| `reimport_sim15.py` | Account-specific one-off |
| `run_calc.bat` | Vague; replace with `Makefile` target |
| `run_full_sync.py` | Superseded by `run_import.py` |
| `run_test_import.py` | Superseded by pytest suite |
| `run_verification_import.py` | Superseded by pytest integration tests |
| `simple_api_server.py` | Dev artifact; superseded by uvicorn start |
| `simulate_import.py` | Superseded by pytest fixtures |
| `stationarity_test.py` | Belongs in `services/statistical/stationarity.py` |
| `test_api_discovery.py` | Superseded by pytest integration tests |
| `thorough_cleanup.py` | Dangerous; vague |
| `trade_reconstructor.py` | Superseded by GFRE fill_pairer.py |
| `trigger_cl_sync.py` | Asset-specific one-off |
| `trigger_import.py` | Superseded by `run_import.py` |
| `trigger_sim15_sync.py` | Account-specific one-off |
| `verify_specific_edges.py` | One-off edge case verifier |
| `wipe_cl.py` | Dangerous; asset-specific |
| `diagnostics/` (subfolder) | Move useful diagnostics to `tests/integration/` |

### Keep (Promote to `/scripts/` operational layer)

| File | Target | Notes |
| :--- | :--- | :--- |
| `run_walk_forward_test.py` | `scripts/run_walk_forward.py` | Core operational |
| `run_permutation_test.py` | `scripts/run_permutation_test.py` | Core operational |
| `run_out_of_sample_audit.py` | `scripts/run_out_of_sample.py` | Core operational |
| `promote_clean_data_to_production.py` | `scripts/promote.py` | Core operational |
| `run_full_import.py` | `scripts/run_import.py` | Core operational |
| `generate_report.py` | `scripts/generate_report.py` | Core operational |
| `start_trading_platform.bat` | `scripts/start.bat` | Startup |
| `start_backend_only.bat` | `scripts/start_backend_only.bat` | Dev utility |
| `start_frontend_only.bat` | `scripts/start_frontend_only.bat` | Dev utility |

### Keep in Tests (Move to `/tests/`)

| File | Target |
| :--- | :--- |
| `tm7_nq_ghost_analysis.py` | `tests/unit/test_ghost_fill_filter.py` (refactor as pytest) |
| `test_fast_days_resync.py` | `tests/integration/test_import_pipeline.py` (refactor) |
| `full_signal_fill_sync.py` | `tests/integration/test_signal_fill_sync.py` (refactor) |
| `find_ghost_creators.py` | `tests/unit/test_ghost_classification.py` (refactor) |

### Keep in Docs

| File | Target |
| :--- | :--- |
| `parse_graphdata_signals.py` | `docs/examples/parse_graphdata_signals.py` |
| `generate_clean_tm7_sequence.py` | `docs/examples/generate_clean_sequence.py` |
| `export_problematic_sequences.py` | Archive in `docs/examples/` |
| `verification_audit_data.json` | `tests/fixtures/verification_audit_data.json` |

### Delete Entirely from Root

| Item | Reason |
| :--- | :--- |
| `trading_platform.db` | Never commit database; add to .gitignore |
| `trading_platform.log` / `.log.old` | Never commit logs; add to .gitignore |
| `ghost_all.log` | Debug log artifact |
| `import_debug.log` | Debug log artifact |
| `import_files_trace.log` | Debug log artifact |
| `scratch_parser_test.db` | Test artifact; add to .gitignore |
| `3/` | Unknown artifact; delete |
| `New folder/` | Unknown artifact; delete |
| `rar_extract/` | Extraction artifact; delete |
| `legacy/` | Move anything useful to archive branch; then delete |
| `scratch/` | Delete entirely; no production value |
| `debug/` | Delete entirely; no production value |
| `models/` (root-level) | Duplicate of `trading_platform/models/`; delete |
| `5x PDF files at root` | Move to `docs/reports/` |
| `ghost_fill_audit.md` | Move to `docs/` |
| `project_deep_dive.md` | Move to `docs/` |
| `.bmad-core/` `.claude/` `.cursor/` `.kiro/` `.qodo/` | Add to .gitignore only |

---

## 4. Backend Architecture (`/backend/`)

### Module Map

```
backend/
|-- core/                  LAYER 0: Configuration and cross-cutting concerns
|-- db/                    LAYER 1: Database engine, sessions, migrations
|-- models/                LAYER 2: ORM models (source of truth for schema)
|-- schemas/               LAYER 3: Pydantic I/O contracts (no ORM objects cross API boundary)
|-- repositories/          LAYER 4: Data access (SQL queries, no business logic)
|-- services/              LAYER 5: Business logic (no HTTP, no SQL direct)
|-- api/                   LAYER 6: HTTP handlers (thin: validate, call service, return schema)
```

**Strict layering rule**: Each layer may only import from layers below it. `api/` imports `services/` and `schemas/`. `services/` imports `repositories/` and `models/`. `repositories/` imports `models/` and `db/`. No layer skips. No upward imports.

### Service Boundaries (Canonical Contracts)

#### `IngestionService`
**Responsibility**: Orchestrate the full binary log import pipeline.
**Inputs**: List of `.data` file paths, account filter list, date range.
**Outputs**: `ImportJobResult` (files processed, fills parsed, ghosts dropped, trades written, duration).
**Key sub-services**: `BinaryLogParser` → `GhostFillFilter` → `FillPairer` → `Deduplicator`.
**Must NOT**: Write directly to `processed_trades`; delegate to `TradeRepository`.

#### `GhostFillFilter`
**Responsibility**: Classify each raw fill candidate as REAL or GHOST.
**Inputs**: `RawFillCandidate` list with `note`, `msg_text`, `timestamp`, `account_name`.
**Outputs**: Filtered list with `suggests_ghost` flag set.
**Key rule**: Adaptive bypass when `note_coverage_rate < 0.25`.
**Must NOT**: Know anything about pairing or PnL.

#### `FillPairer`
**Responsibility**: FIFO pairing of clean fills into round-trip trades.
**Inputs**: Sorted list of clean `RawFillCandidate` objects.
**Outputs**: List of `CompletedTrade` objects (entry_time, exit_time, direction, pnl).
**Must NOT**: Touch the database; must be stateless and testable in isolation.

#### `PerformanceCalculator`
**Responsibility**: Compute all performance metrics for a set of trades.
**Inputs**: List of `ProcessedTrade` objects + optional config (benchmark rate, risk-free rate).
**Outputs**: `PerformanceSnapshot` (win_rate, net_pnl, sortino, max_drawdown, profit_factor, sharpe).
**Must NOT**: Query the database; caller fetches trades via repository.

#### `TimeBinAnalyzer`
**Responsibility**: Bucket trades into time slots and rank by performance.
**Inputs**: List of `ProcessedTrade` objects, resolution (15min/30min/1h), timezone (default NY).
**Outputs**: `TimeBinGrid` — dict of `{slot_label: TimeBinMetrics}`.

#### `WalkForwardEngine`
**Responsibility**: Execute walk-forward validation across configurable in-sample/out-of-sample windows.
**Inputs**: `ProcessedTrade` list, `WalkForwardConfig` (n_folds, is_ratio, oos_ratio).
**Outputs**: `WalkForwardResult` (per-fold metrics, degradation curve, BH-FDR gate result).

#### `MonteCarloEngine`
**Responsibility**: Simulate N equity paths by resampling daily trade PnL.
**Inputs**: `ProcessedTrade` list, `MonteCarloConfig` (n_simulations, horizon_days, confidence_levels).
**Outputs**: `MonteCarloResult` (percentile curves, VaR, CVaR, max_drawdown distribution).

#### `StatisticalTestingEngine`
**Responsibility**: Apply BH-FDR multiple testing correction and permutation tests.
**Inputs**: Raw p-values from all time-bin tests, alpha level, n_permutations.
**Outputs**: `FDRResult` (adjusted p-values, rejected hypotheses, promotion decisions).
**Critical**: This is the gateway for the BH-FDR promotion gate. Nothing promotes to production without passing this.

#### `RecommendationEngine`
**Responsibility**: Generate actionable trade schedule recommendations.
**Inputs**: `TimeBinGrid`, `WalkForwardResult`, `FDRResult`, `AccountConfig`.
**Outputs**: `RecommendationSet` (ranked time windows, risk-adjusted position sizing, confidence scores).

### Service Interface Pattern

Every service must implement a typed interface using Python `Protocol`:

```python
# backend/services/ingestion/protocols.py
from typing import Protocol, Sequence
from backend.schemas.import_job import ImportJobResult
from backend.schemas.trade import RawFillCandidate

class GhostFillFilterProtocol(Protocol):
    def filter(
        self,
        candidates: Sequence[RawFillCandidate],
        account_name: str,
    ) -> Sequence[RawFillCandidate]: ...

class FillPairerProtocol(Protocol):
    def pair(
        self,
        clean_fills: Sequence[RawFillCandidate],
    ) -> Sequence[dict]: ...
```

This enables:
1. Mock injection in tests without modifying production classes
2. Clear contract documentation visible from the interface definition
3. Static type checking (mypy) across service boundaries

---

## 5. Database Layer and Migration Path

### Current State
- SQLite at `trading_platform.db` (root level, committed to VCS)
- Alembic exists but is not wired to `trading_platform/models/`
- No migration history — schema was created manually

### Target: SQLAlchemy + Alembic, PostgreSQL-Ready

#### Step 1: Single Declarative Base
```python
# backend/db/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# All ORM models import from here — never from anywhere else
```

#### Step 2: Alembic Wired to Models
```python
# backend/alembic/env.py
from backend.db.base import Base
from backend.models import trade, account, analytics, import_job  # noqa — register models
target_metadata = Base.metadata
```

#### Step 3: Connection String Abstraction
```python
# backend/core/config.py
class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/trading_platform.db"
    # Override with:
    # DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/sc_results
```

#### SQLite → PostgreSQL Migration Path

| Phase | Action | Risk |
| :--- | :--- | :--- |
| Now | Stay on SQLite; enforce Alembic | Low |
| Phase 4 | Add `DATABASE_URL` env var; test PostgreSQL locally via docker-compose | Low |
| Phase 4 | Run `alembic upgrade head` against PG instance | Medium |
| Phase 4 | `pg_dump` / `pg_restore` for data migration | Medium |
| Phase 5 | Switch production `DATABASE_URL` to PG; remove SQLite default | Low |

#### PostgreSQL docker-compose (Phase 4 Preview)
```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: sc_results
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/sc_results
    depends_on:
      - postgres
```

#### Index Strategy for `processed_trades`

```sql
-- Covering index for the most common query pattern: account + symbol + date range
CREATE INDEX idx_pt_acc_sym_entry ON processed_trades(account_name, symbol, entry_time);

-- For time-bin analysis queries (NY minute bucketing)
CREATE INDEX idx_pt_minute_ny ON processed_trades(minute_of_hour_ny, account_name);

-- For leaderboard queries (sortino per account)
CREATE INDEX idx_pt_acc_pnl ON processed_trades(account_name, profit_loss);
```

---

## 6. API Design — Versioned Routes

### Base URL Structure
```
/api/v1/{domain}/{resource}
```

All routes return `application/json`. All error responses follow RFC 7807 (Problem Details).

### Domain: Trades — `/api/v1/trades`

| Method | Path | Description | Response |
| :--- | :--- | :--- | :--- |
| GET | `/api/v1/trades` | Paginated trade list | `Page[TradeSchema]` |
| GET | `/api/v1/trades/{trade_id}` | Single trade detail | `TradeSchema` |
| GET | `/api/v1/trades/summary` | Daily/weekly PnL summary | `TradeSummarySchema` |
| DELETE | `/api/v1/trades/{trade_id}` | Remove single trade (admin) | `204 No Content` |

### Domain: Analytics — `/api/v1/analytics`

| Method | Path | Description | Response |
| :--- | :--- | :--- | :--- |
| GET | `/api/v1/analytics/performance` | Full performance metrics | `PerformanceSnapshot` |
| GET | `/api/v1/analytics/time-bins` | Time-bin performance grid | `TimeBinGrid` |
| GET | `/api/v1/analytics/sortino-leaderboard` | Ranked accounts by Sortino | `List[AccountRanking]` |
| GET | `/api/v1/analytics/drawdown` | Drawdown curve (equity series) | `DrawdownSeries` |
| GET | `/api/v1/analytics/pnl-curve` | Cumulative PnL over time | `PnLCurveSeries` |

### Domain: Accounts — `/api/v1/accounts`

| Method | Path | Description | Response |
| :--- | :--- | :--- | :--- |
| GET | `/api/v1/accounts` | List all accounts | `List[AccountSchema]` |
| GET | `/api/v1/accounts/{name}` | Account config + last import | `AccountDetailSchema` |
| GET | `/api/v1/accounts/{name}/symbols` | Symbols traded in account | `List[str]` |
| PUT | `/api/v1/accounts/{name}/config` | Update account config | `AccountSchema` |

### Domain: Walk-Forward — `/api/v1/walkforward`

| Method | Path | Description | Response |
| :--- | :--- | :--- | :--- |
| POST | `/api/v1/walkforward/run` | Start WF test (async job) | `ImportJobSchema` (job_id) |
| GET | `/api/v1/walkforward/jobs/{job_id}` | Poll job status | `JobStatusSchema` |
| GET | `/api/v1/walkforward/results/{job_id}` | Retrieve WF results | `WalkForwardResult` |
| GET | `/api/v1/walkforward/latest` | Most recent WF result | `WalkForwardResult` |

### Domain: Recommendations — `/api/v1/recommendations`

| Method | Path | Description | Response |
| :--- | :--- | :--- | :--- |
| GET | `/api/v1/recommendations` | Current recommendations | `RecommendationSet` |
| GET | `/api/v1/recommendations/{account}` | Account-specific recommendations | `RecommendationSet` |
| POST | `/api/v1/recommendations/refresh` | Recompute recommendations | `JobStatusSchema` |

### Domain: Import Jobs — `/api/v1/import`

| Method | Path | Description | Response |
| :--- | :--- | :--- | :--- |
| POST | `/api/v1/import/trigger` | Trigger full binary log import | `ImportJobSchema` |
| GET | `/api/v1/import/jobs` | List recent import jobs | `List[ImportJobSchema]` |
| GET | `/api/v1/import/jobs/{job_id}` | Job status + progress | `ImportJobStatusSchema` |

### Common Query Parameters

All list endpoints support:
```
?account=TM_7           # Filter by account name
?symbol=FDAXM26         # Filter by symbol
?from=2026-06-01        # Start date (ISO 8601)
?to=2026-07-23          # End date (ISO 8601)
?page=1&page_size=50    # Pagination
```

### Response Schema Examples

```typescript
// PerformanceSnapshot
{
  account_name: string,
  symbol: string | null,
  period_start: string,           // ISO 8601
  period_end: string,
  trade_count: number,
  win_count: number,
  loss_count: number,
  win_rate: number,               // 0.0 - 1.0
  net_pnl: number,                // USD
  gross_profit: number,
  gross_loss: number,
  profit_factor: number,
  max_drawdown: number,           // USD
  max_drawdown_pct: number,       // 0.0 - 1.0
  sortino_ratio: number,
  sharpe_ratio: number,
  avg_trade_duration_min: number,
  largest_win: number,
  largest_loss: number
}

// TimeBinGrid
{
  resolution: "15min" | "30min" | "1h",
  timezone: "America/New_York",
  slots: {
    "09:30": {
      trade_count: number,
      win_rate: number,
      avg_pnl: number,
      total_pnl: number,
      sortino: number,
      fdr_promoted: boolean       // Has this slot passed BH-FDR gate?
    },
    ...
  }
}
```

---

## 7. Frontend Architecture (`/frontend/`)

### Component Hierarchy: Feature Module Pattern

Replace the current `pages/` + flat `components/` structure with vertical feature slices. Each feature is self-contained with its own components, hooks, and API calls. Only truly shared UI elements live in `shared/`.

```
frontend/src/
|-- app/
|   |-- App.tsx                <- Root, theme, global providers
|   |-- router.tsx             <- React Router v6 routes
|
|-- features/
|   |-- dashboard/             <- Overview KPIs and charts
|   |   |-- DashboardPage.tsx
|   |   |-- components/
|   |   |   |-- KPIGrid.tsx
|   |   |   |-- PnLCurveChart.tsx
|   |   |   |-- DrawdownChart.tsx
|   |   |-- hooks/
|   |   |   |-- useDashboardData.ts
|   |   |-- dashboard.slice.ts <- Redux slice
|   |
|   |-- analytics/             <- Time-bin heatmaps, performance breakdown
|   |   |-- AnalyticsPage.tsx
|   |   |-- components/
|   |   |   |-- TimeBinHeatmap.tsx
|   |   |   |-- PerformanceBreakdown.tsx
|   |   |   |-- SortinoLeaderboard.tsx   <- Move from root components/
|   |   |-- hooks/
|   |   |   |-- useTimeBins.ts
|   |   |   |-- useLeaderboard.ts
|   |   |-- analytics.slice.ts
|   |
|   |-- accounts/              <- Account management and trade history
|   |   |-- AccountsPage.tsx
|   |   |-- AccountDetailPage.tsx
|   |   |-- components/
|   |   |   |-- AccountCard.tsx
|   |   |   |-- TradeHistoryTable.tsx
|   |   |-- accounts.slice.ts
|   |
|   |-- walkforward/           <- Walk-forward test runner and results
|   |   |-- WalkForwardPage.tsx
|   |   |-- components/
|   |   |   |-- WalkForwardResultsChart.tsx
|   |   |   |-- FoldComparisonMatrix.tsx
|   |   |   |-- BHFDRGateStatus.tsx
|   |   |-- hooks/
|   |   |   |-- useWalkForwardJob.ts    <- Polls job status
|   |   |-- walkforward.slice.ts
|   |
|   |-- recommendations/       <- Strategy recommendations
|   |   |-- RecommendationsPage.tsx
|   |   |-- components/
|   |   |   |-- RecommendationMatrix.tsx
|   |   |   |-- StrategyValidation.tsx
|   |   |   |-- MonteCarloChart.tsx
|   |   |-- recommendations.slice.ts
|   |
|   |-- import/                <- Import job trigger and progress
|   |   |-- ImportPage.tsx
|   |   |-- components/
|   |   |   |-- ImportJobCard.tsx
|   |   |   |-- ImportProgressBar.tsx
|   |   |-- hooks/
|   |   |   |-- useImportJob.ts         <- Polls import status
|   |
|   |-- monitoring/            <- Alerts and system health
|   |   |-- MonitoringPage.tsx
|   |   |-- components/
|   |   |   |-- AlertsPanel.tsx
|   |   |   |-- SystemHealthCard.tsx
|
|-- shared/
|   |-- charts/                <- Chart wrappers (Plotly.js or Recharts)
|   |   |-- LineChart.tsx      <- Generic reusable line chart
|   |   |-- HeatmapChart.tsx
|   |   |-- BarChart.tsx
|   |-- ui/                    <- Design system components
|   |   |-- Button.tsx
|   |   |-- Card.tsx
|   |   |-- Badge.tsx
|   |   |-- Table.tsx
|   |   |-- Spinner.tsx
|   |   |-- MetricCard.tsx     <- Reusable KPI tile
|   |-- layout/
|   |   |-- Layout.tsx
|   |   |-- Sidebar.tsx
|   |   |-- Header.tsx
|   |-- hooks/
|   |   |-- useApiQuery.ts     <- Typed wrapper over fetch/axios
|   |   |-- useJobPoller.ts    <- Generic async job poller
|
|-- store/
|   |-- store.ts               <- Redux store configuration
|   |-- slices/
|   |   |-- dashboard.slice.ts
|   |   |-- analytics.slice.ts
|   |   |-- accounts.slice.ts
|   |   |-- walkforward.slice.ts
|   |   |-- recommendations.slice.ts
|   |   |-- import.slice.ts
|
|-- services/
|   |-- api.ts                 <- Base axios/fetch config (base URL, auth headers)
|   |-- trades.api.ts          <- /api/v1/trades calls
|   |-- analytics.api.ts       <- /api/v1/analytics calls
|   |-- accounts.api.ts        <- /api/v1/accounts calls
|   |-- walkforward.api.ts     <- /api/v1/walkforward calls
|   |-- recommendations.api.ts <- /api/v1/recommendations calls
|   |-- import.api.ts          <- /api/v1/import calls
|
|-- types/
|   |-- api.ts                 <- Auto-generated from OpenAPI spec (Phase 3)
|   |-- common.ts              <- Shared types
```

### State Management: Redux Toolkit Slice Pattern

Each feature slice owns:
- Server data (fetched trades, analytics results)
- Loading / error state
- Local UI state (selected filters, date ranges, open modals)
- Async thunks for API calls

```typescript
// features/analytics/analytics.slice.ts
interface AnalyticsState {
  timeBins: TimeBinGrid | null;
  leaderboard: AccountRanking[];
  performance: PerformanceSnapshot | null;
  selectedAccount: string | null;
  selectedSymbol: string | null;
  dateRange: { from: string; to: string };
  status: "idle" | "loading" | "succeeded" | "failed";
  error: string | null;
}

// Async thunks
export const fetchTimeBins = createAsyncThunk(...)
export const fetchLeaderboard = createAsyncThunk(...)
export const fetchPerformance = createAsyncThunk(...)
```

### Chart Layer: Plotly.js Integration

All charts wrap Plotly.js via `react-plotly.js`. A thin wrapper in `shared/charts/` handles:
- Consistent theme (dark mode, color palette matching the design system)
- Responsive sizing via `useContainerSize` hook
- Loading skeleton state
- Error fallback

```typescript
// shared/charts/LineChart.tsx
interface LineChartProps {
  series: PlotData[];          // Plotly data format
  title?: string;
  xLabel?: string;
  yLabel?: string;
  height?: number;
  isLoading?: boolean;
}
```

Feature components never call Plotly directly — they format data into `PlotData[]` and pass to the wrapper.

---

## 8. Data Flow Pipeline (End-to-End)

### Ingestion Pipeline

```
[Sierra Chart Platform]
    |
    | Writes .data files to dataset/ directory
    v
[ImportOrchestrator.run(file_paths, account_filter, date_range)]
    |
    | Spawns ProcessPoolExecutor (CPU - 1 workers)
    | Each worker runs: BinaryLogParser._parse_file_nitro(file_path)
    v
[Per-File Results]
    |
    | Stage 1: GhostFillFilter.filter(raw_candidates)
    |   - Check Tag 0x82 for AutoTrader_ prefix
    |   - Adaptive bypass if note_coverage_rate < 0.25
    |   - Flag suggests_ghost on Trade Evaluator fills without notes
    v
[Clean Fill Candidates per file]
    |
    | Stage 2: Deduplicator.dedup_per_file(candidates, window_ms=250)
    |   - Key: (ts_bucket_250ms, price, side, qty, account, order_id)
    v
[Per-File Deduplicated Fills]
    |
    | Merge all file results
    |
    | Stage 3: Deduplicator.dedup_global(all_fills, window_s=2)
    |   - Key: (ts_bucket_2s, price, side, qty, account, symbol)
    v
[Global Deduplicated Fill Stream]
    |
    | Stage 4: FillPairer.pair(sorted_fills)
    |   - FIFO queue per (account, symbol)
    |   - Entry fill → push to open_positions
    |   - Exit fill → pop from open_positions → CompletedTrade
    |   - EOD flatten → close remaining positions at 17:00 NY
    v
[CompletedTrade list]
    |
    | Stage 5: SequenceIntegrityVerifier.verify(trades)
    |   - Assert position closes to 0 at session boundaries
    |   - Assert no orphaned entries remain
    v
[Verified CompletedTrade list]
    |
    | Stage 6: TradeRepository.bulk_upsert(trades)
    |   - Upsert to staging table first
    |   - Apply outlier filter (duration > 24h, PnL > 3σ)
    |   - Promote to processed_trades
    v
[processed_trades table — SQLite / PostgreSQL]
    |
    | Stage 7 (optional): StatisticalTestingEngine.bh_fdr_gate(time_bins)
    |   - Apply BH-FDR correction to all time-bin p-values
    |   - Promote passing time slots to production_time_bins view
    v
[production_time_bins view — BH-FDR promoted slots only]
```

### API → Frontend Contract Flow

```
[React Component]
    |
    | dispatch(fetchTimeBins({ account: "TM_7", symbol: "FDAXM26" }))
    v
[analytics.api.ts → GET /api/v1/analytics/time-bins?account=TM_7&symbol=FDAXM26]
    |
    v
[FastAPI Route: analytics.py]
    |
    | Validates query params via Pydantic
    | Calls TimeBinAnalyzer.analyze(account, symbol, date_range)
    v
[TimeBinAnalyzer]
    |
    | Calls MetricsRepository.get_trades_in_range(account, symbol, from, to)
    | Buckets trades by NY minute slot
    | Computes per-slot: win_rate, avg_pnl, sortino, fdr_promoted
    v
[Returns TimeBinGrid schema]
    |
    v
[FastAPI serializes to JSON]
    |
    v
[analytics.slice.ts updates Redux store]
    |
    v
[TimeBinHeatmap.tsx reads from selector → renders Plotly heatmap]
```

### Long-Running Job Pattern

Walk-forward and Monte Carlo jobs are too slow for synchronous HTTP. Use FastAPI `BackgroundTasks` for Phase 1-3, upgrade to Celery for Phase 5:

```
POST /api/v1/walkforward/run
    |
    | Creates ImportJob record with status=PENDING
    | Returns { job_id: "wf_abc123", status: "PENDING" }
    |
    | FastAPI BackgroundTask: WalkForwardEngine.run_async(job_id, config)
    |   → Updates job status: PENDING → RUNNING → COMPLETE
    |   → Writes results to walkforward_results table
    v
[Frontend: useJobPoller polls GET /api/v1/walkforward/jobs/{job_id} every 3s]
    |
    | job.status == "COMPLETE" → dispatch(fetchWalkForwardResults(job_id))
    v
[WalkForwardResultsChart.tsx renders results]
```

---

## 9. Five-Phase Development Roadmap

### Phase 1: Repo Cleanup + Structure Enforcement (2 Weeks)

**Goal**: Zero root-level chaos. Clear module boundaries. Any new contributor can orient in 5 minutes.

**Tasks**:
- [ ] Create `archive` git branch; move all delete-candidates there before deleting from `main`
- [ ] Delete 60+ throwaway scripts from `scripts/` (see Deletion Manifest)
- [ ] Move `trading_platform/` → `backend/`; update all imports
- [ ] Delete root-level `models/`, `legacy/`, `scratch/`, `debug/`
- [ ] Move `main.py` to `backend/api/app.py`; create `backend/main.py` as uvicorn shim
- [ ] Move `alembic/` + `alembic.ini` → `backend/alembic/`
- [ ] Move `requirements.txt` → `backend/requirements.txt`
- [ ] Wire Alembic to `backend/models/` (fix `env.py`)
- [ ] Add `trading_platform.db`, `*.log`, `*.log.old`, `scratch_parser_test.db` to `.gitignore`
- [ ] Move all root `.md` files → `docs/`; move PDFs → `docs/reports/`
- [ ] Move `docker-compose.yml`, `Dockerfile` → `infra/`
- [ ] Create `Makefile` with targets: `dev`, `test`, `migrate`, `import`, `lint`
- [ ] Update `README.md` to reflect new structure
- [ ] Update `PROJECT_OVERVIEW.md` with new paths
- [ ] Commit: "chore: Phase 1 monorepo restructure"

**Success Criteria**: `find . -maxdepth 1 -name "*.py" | wc -l` returns 0 at root.

---

### Phase 2: Backend Stabilization + Test Coverage (3 Weeks)

**Goal**: 80%+ unit test coverage on core pipeline. All services use typed interfaces. Alembic migrations functional.

**Tasks**:
- [ ] Extract `GhostFillFilter` class from `binary_log_parser.py` into `services/ingestion/ghost_fill_filter.py`
- [ ] Extract `FillPairer` into `services/ingestion/fill_pairer.py`
- [ ] Extract `Deduplicator` into `services/ingestion/deduplicator.py`
- [ ] Create `ImportOrchestrator` in `services/ingestion/import_orchestrator.py`
- [ ] Write service `Protocol` interfaces for all 8 core services
- [ ] Write pytest unit tests for:
  - `GhostFillFilter` (ghost/real classification matrix, 20+ cases)
  - `FillPairer` (FIFO pairing, flip detection, EOD flatten)
  - `PerformanceCalculator` (sortino, drawdown, win rate)
  - `StatisticalTestingEngine` (BH-FDR correction, permutation test)
- [ ] Write pytest integration tests for:
  - Full import pipeline against `tests/fixtures/sample_binary_log.data`
  - API endpoints: trades, analytics, accounts (use TestClient)
- [ ] Run Alembic `autogenerate` and create initial migration `0001_initial.py`
- [ ] Add `pre-commit` hooks: `black`, `isort`, `mypy --strict` for `backend/`
- [ ] Add `pytest --cov=backend --cov-report=term-missing` to CI

**Success Criteria**: `pytest tests/` passes with ≥80% coverage on `backend/services/ingestion/`.

---

### Phase 3: Frontend Refactor + Component Library (3 Weeks)

**Goal**: Feature-module structure. No orphaned components. TypeScript strict mode. Auto-generated API types.

**Tasks**:
- [ ] Install and configure `openapi-typescript` to generate `frontend/src/types/api.ts` from FastAPI's `/openapi.json`
- [ ] Add this to CI: `make generate-types` fails build if types are out of date
- [ ] Migrate `pages/` to `features/` structure (7 features)
- [ ] Move feature-specific components from flat `components/` into their feature modules
- [ ] Move truly shared components (MetricCard, Layout, ErrorBoundary) to `shared/`
- [ ] Move `SortinoLeaderboard.tsx` from flat `components/` → `features/analytics/components/`
- [ ] Create `shared/charts/` wrappers for all 6 chart types used
- [ ] Add Redux slice for `import` feature (currently missing)
- [ ] Add Redux slice for `walkforward` feature (currently missing)
- [ ] Add `useJobPoller` hook for async job status polling
- [ ] Enable TypeScript strict mode in `tsconfig.json`
- [ ] Add `eslint` + `prettier` to frontend CI
- [ ] Add Storybook for `shared/ui/` components

**Success Criteria**: `tsc --noEmit` passes with `strict: true`. All components are inside `features/` or `shared/`. No orphaned `.tsx` files in `components/`.

---

### Phase 4: PostgreSQL Migration + Performance Tuning (2 Weeks)

**Goal**: Database ready for production scale. Sub-100ms API response times for all standard queries.

**Tasks**:
- [ ] Add `postgres:16-alpine` service to `infra/docker-compose.yml`
- [ ] Parameterize `DATABASE_URL` in `backend/core/config.py`
- [ ] Run Alembic migrations against local PostgreSQL instance
- [ ] Data migration: `sqlite3` export → `pg_restore` pipeline script
- [ ] Add covering indexes (see Database Layer section)
- [ ] Add query execution plan logging (`EXPLAIN ANALYZE`) for top 10 query patterns
- [ ] Add Redis cache layer for `TimeBinAnalyzer` results (cache TTL: 5 min)
- [ ] Add API response caching headers for static analytics
- [ ] Load test: simulate 50 concurrent dashboard loads with `locust`
- [ ] Target: all dashboard API calls < 100ms at p95

**Success Criteria**: All 5 API domain queries complete in < 100ms p95 under 50 concurrent users against PostgreSQL.

---

### Phase 5: CI/CD + Docker Production Hardening (2 Weeks)

**Goal**: Deployable production stack. Automated pipeline from push to deploy. Zero secrets in code.

**Tasks**:
- [ ] Finalize `infra/docker/Dockerfile.backend` (multi-stage: builder + runtime, non-root user)
- [ ] Finalize `infra/docker/Dockerfile.frontend` (multi-stage: node builder + nginx)
- [ ] Create `infra/docker-compose.prod.yml` (no volume mounts, env from secrets manager)
- [ ] GitHub Actions `ci.yml`: lint → test → build → push Docker image to GHCR
- [ ] GitHub Actions `deploy.yml`: pull from GHCR → rolling restart (manual trigger or tag-based)
- [ ] Upgrade long-running jobs (WF, Monte Carlo) from `BackgroundTasks` to Celery + Redis
- [ ] Add `/api/v1/health` endpoint with DB connection check + last import timestamp
- [ ] Add structured JSON logging throughout backend (replace print/logging.info)
- [ ] Add Sentry error tracking (backend + frontend)
- [ ] Add rate limiting middleware (slowapi) for production API exposure
- [ ] Secrets: move all credentials to GitHub Actions secrets + runtime environment injection

**Success Criteria**: `git push` triggers CI. Green CI → deployable image. No secrets in any committed file.

---

## 10. Security and Configuration Design

### `.env` Variable Inventory

```bash
# ── Backend ───────────────────────────────────────────────────────────────────
DATABASE_URL=sqlite:///./data/trading_platform.db
# Prod: DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/sc_results

SECRET_KEY=<32-byte random hex>         # JWT signing key
API_KEY=<uuid4>                          # Simple API key for external clients
ACCESS_TOKEN_EXPIRE_MINUTES=1440         # 24 hours

ALLOWED_ORIGINS=http://localhost:3000    # CORS whitelist
# Prod: ALLOWED_ORIGINS=https://yourdomain.com

DATASET_PATH=./dataset                   # Root path for .data file scanning
DATA_PATH=./data                         # Writable data directory (DB, logs)
LOG_LEVEL=INFO                           # DEBUG / INFO / WARNING / ERROR

REDIS_URL=redis://localhost:6379/0       # For Celery (Phase 5) and caching

# ── Sentry (Phase 5) ──────────────────────────────────────────────────────────
SENTRY_DSN=

# ── External Market Data ──────────────────────────────────────────────────────
ALPHA_VANTAGE_KEY=                       # For VIX regime data
QUANDL_KEY=

# ── Frontend (Vite) ───────────────────────────────────────────────────────────
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws       # WebSocket (Phase 5)
```

### Secrets Management Rules

1. **Never commit `.env`** — it is in `.gitignore`. Only `.env.example` is committed.
2. **No hardcoded credentials anywhere in code** — all values from `Settings` class.
3. **Rotate `SECRET_KEY`** on every deployment environment.
4. **`API_KEY` auth** for all `/api/v1/` routes in production (Bearer token header).
5. **GitHub Actions**: use `secrets.DATABASE_URL`, `secrets.SECRET_KEY`, etc. Never in YAML values.

### CORS Policy

```python
# backend/api/middleware.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**Development**: `ALLOWED_ORIGINS=http://localhost:3000`
**Production**: `ALLOWED_ORIGINS=https://yourdomain.com` (no wildcard)

### API Key Auth Pattern

```python
# backend/core/security.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(key: str = Security(api_key_header)):
    if key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

# Apply to all routes:
app.include_router(v1_router, dependencies=[Depends(verify_api_key)])
```

---

## 11. Technology Decisions

### Decision 1: SQLite vs PostgreSQL

| Factor | SQLite (Now) | PostgreSQL (Phase 4+) |
| :--- | :--- | :--- |
| Setup complexity | Zero | Requires Docker |
| Concurrent writers | 1 (WAL mode: limited) | Unlimited |
| Dataset at 606K+ trades | Adequate | Better index performance |
| Alembic support | Full | Full |
| Cloud deployment | Problematic (no persistent volume) | Native |
| **Recommendation** | **Keep through Phase 3** | **Migrate at Phase 4** |

**Verdict**: Stay on SQLite with WAL mode enabled until Phase 4. The schema is abstracted via SQLAlchemy — migration is a connection string change.

### Decision 2: WebSocket vs Polling for Live P&L

| Factor | WebSocket | Polling (current) |
| :--- | :--- | :--- |
| Real-time latency | < 100ms | 3-5 seconds |
| Infrastructure complexity | Redis pub/sub required | None |
| Browser support | Universal | Universal |
| Reconnection handling | Must implement | Free (fetch retry) |
| Value for trading analytics | Medium (not HFT) | Sufficient |
| **Recommendation** | **Phase 5 optional** | **Default through Phase 4** |

**Verdict**: Polling every 3-5 seconds is sufficient for a trading analytics dashboard (not a live order management system). Implement WebSocket in Phase 5 only if users explicitly need sub-second P&L updates.

### Decision 3: Celery vs FastAPI BackgroundTasks for Long-Running Jobs

| Factor | BackgroundTasks | Celery + Redis |
| :--- | :--- | :--- |
| Setup complexity | Zero | Requires Redis + worker process |
| Job persistence | None (lost on restart) | Persisted in Redis |
| Job status tracking | Manual (DB polling) | Native Flower UI |
| Concurrency control | Limited | Full queue management |
| Good for jobs < 30s | Yes | Overkill |
| Good for jobs > 30s | Risk of timeout | Yes |
| **WalkForward (1-2 min)** | Marginal | Better |
| **MonteCarlo (5-10 min)** | Risk | Yes |
| **Recommendation** | **Phases 1-3** | **Phase 5** |

**Verdict**: Use `BackgroundTasks` through Phase 3 with DB-backed job status. Migrate to Celery in Phase 5 when deploying to production with multi-worker setup.

### Decision 4: Plotly.js vs Recharts vs D3

| Factor | Plotly.js | Recharts | D3 |
| :--- | :--- | :--- | :--- |
| Already in codebase | Yes | Yes (partial) | No |
| Scientific chart types | Best (OHLC, heatmap, histogram) | Limited | Anything |
| Bundle size | Large (~3MB) | Medium (~400KB) | Small (modular) |
| React integration | `react-plotly.js` | Native React | Manual |
| Customization | Via layout config | Via props | Unlimited |
| **Recommendation** | **Keep Plotly.js** | **Remove** | **No** |

**Verdict**: Standardize on Plotly.js via `shared/charts/` wrappers. Remove Recharts. The heatmap, OHLC, and distribution chart types justify the bundle size for a data-heavy analytics app.

---

## 12. Makefile Task Runner

```makefile
# Makefile — Unified task runner for SC Results WF Platform

.PHONY: dev test lint migrate import report clean

# ── Development ──────────────────────────────────────────────────────────────
dev:
	@echo "Starting backend + frontend..."
	concurrently "make backend" "make frontend"

backend:
	cd backend && uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# ── Database ─────────────────────────────────────────────────────────────────
migrate:
	cd backend && alembic upgrade head

migrate-rollback:
	cd backend && alembic downgrade -1

migrate-create:
	cd backend && alembic revision --autogenerate -m "$(msg)"

# ── Testing ──────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --cov=backend --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

# ── Linting ──────────────────────────────────────────────────────────────────
lint:
	cd backend && black . && isort . && mypy . --ignore-missing-imports
	cd frontend && npm run lint

# ── Pipeline Operations ──────────────────────────────────────────────────────
import:
	python scripts/run_import.py

walkforward:
	python scripts/run_walk_forward.py

permutation-test:
	python scripts/run_permutation_test.py

oos:
	python scripts/run_out_of_sample.py

promote:
	python scripts/promote.py

report:
	python scripts/generate_report.py

# ── Cleanup ──────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true

# ── Docker ───────────────────────────────────────────────────────────────────
docker-up:
	docker-compose -f infra/docker-compose.yml up --build

docker-down:
	docker-compose -f infra/docker-compose.yml down

docker-prod:
	docker-compose -f infra/docker-compose.prod.yml up -d
```

---

*Blueprint Version: 1.0 | Author: Principal Architect Review | July 26, 2026*
*Next Review: After Phase 1 completion*
