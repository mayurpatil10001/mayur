# Codebase Cleanup Log

All files moved or deleted during the July 2026 repository audit.
Scripts were categorized using the following decision matrix:

- **Moved → `scripts/diagnostics/`**: Reusable, single-purpose diagnostic scripts with value as future reference tools.
- **Deleted**: One-time debugging or iteration scripts superseded by superior/combined versions, or empty stubs.

---

## Root-Level Scripts: Categorized (71 files)

> `main.py` is the application entry point and is NOT part of this cleanup.

### Moved to `scripts/diagnostics/`

These scripts have ongoing diagnostic value and were moved with a docstring added.

| Original Filename | Moved To | Reason |
| :--- | :--- | :--- |
| `binary_vs_db_compare.py` | `scripts/diagnostics/binary_vs_db_compare.py` | Core binary parser vs DB field comparison — reference verification tool |
| `compare_tm7_rar.py` | `scripts/diagnostics/compare_tm7_rar.py` | TM_7 NQ RAR activity log vs processed_trades comparison |
| `direct_parse_compare.py` | `scripts/diagnostics/direct_parse_compare.py` | Standalone binary parser vs DB side-by-side audit |
| `final_verify_compare.py` | `scripts/diagnostics/final_verify_compare.py` | Final field-level binary vs DB verification |
| `import_and_compare_tm7.py` | `scripts/diagnostics/import_and_compare_tm7.py` | TM_7 binary import and comparison pipeline |
| `verify_system_import.py` | `scripts/diagnostics/verify_system_import.py` | RAR import consistency verification |
| `monthly_stats.py` | `scripts/diagnostics/monthly_stats.py` | Monthly trade count and PnL breakdown by month |
| `trade_folder_stats.py` | `scripts/diagnostics/trade_folder_stats.py` | Dataset folder file count and size statistics |
| `count_all_data.py` | `scripts/diagnostics/count_all_data.py` | Total data volume counter across all dataset folders |
| `find_continuous_accounts.py` | `scripts/diagnostics/find_continuous_accounts.py` | Identifies accounts with continuous data ranges |
| `find_outliers.py` | `scripts/diagnostics/find_outliers.py` | Identifies PnL outlier trades in DB |
| `check_active_ranges.py` | `scripts/diagnostics/check_active_ranges.py` | Verifies account date ranges are correct |
| `check_db_state.py` | `scripts/diagnostics/check_db_state.py` | Snapshot of DB row counts per table |
| `check_indices.py` | `scripts/diagnostics/check_indices.py` | Verifies SQLite indexes are built correctly |
| `integrate_advanced_recommendations.py` | `scripts/diagnostics/integrate_advanced_recommendations.py` | Integration test for ML recommendation engine |
| `create_agg_index.py` | `scripts/diagnostics/create_agg_index.py` | Creates aggregate index for time-bin queries |
| `create_index.py` | `scripts/diagnostics/create_index.py` | Creates standard DB query index |
| `create_ultimate_index.py` | `scripts/diagnostics/create_ultimate_index.py` | Creates full composite index for analytics queries |
| `analyze_outlier_month.py` | `scripts/diagnostics/analyze_outlier_month.py` | Analyzes specific months showing PnL outliers |
| `verify_db.py` | `scripts/diagnostics/verify_db.py` | General DB state verification script |
| `verify_cache.py` | `scripts/diagnostics/verify_cache.py` | Verifies time-bin cache state vs live DB |

### Deleted (One-Time Debug Scripts — Purpose Superseded)

These scripts served single-session debugging purposes and are fully superseded by the scripts moved above, the consolidated audit reports, or the formal test suite. Every file is listed below with its reason for deletion.

| Filename | Reason for Deletion |
| :--- | :--- |
| `check_2024_active_accounts.py` | Superseded by `check_active_ranges.py` (moved) |
| `check_2024_db.py` | One-time API HTTP check for 2024 data counts; result captured in audit |
| `check_all_jan_mar.py` | One-time check for Jan-Mar data; superseded by `verify_jan_mar.py` |
| `check_all_sim16.py` | V500_SIM16 one-time data scan |
| `check_all_sim16_v2.py` | V2 iteration of above; superseded by v3 |
| `check_all_sim16_v3.py` | Final V500_SIM16 check; results captured in audit |
| `check_api_accounts.py` | One-time API endpoint test; covered by `tests/test_accounts_api.py` |
| `check_api_debug.py` | One-time API debug HTTP probe |
| `check_backend.py` | One-time health check; covered by `/health` endpoint |
| `check_files.py` | One-time dataset folder file existence check |
| `check_import_errors.py` | One-time import error scanner; error log analysis complete |
| `check_inst4_jan_mar.py` | One-time INSTANCE4 Jan-Mar check |
| `check_instance4.py` | One-time INSTANCE4 dataset probe |
| `check_main.py` | One-time parser main() call; one-session debug |
| `check_outlier_days.py` | Outlier day analysis; results captured in `analyze_outlier_month.py` |
| `check_txt_dates.py` | One-time `.txt` date range scan |
| `check_v500_sim16.py` | One-time V500_SIM16 scan |
| `check_v500_sim16_stats.py` | One-time V500_SIM16 stats; superseded by `monthly_stats.py` |
| `check_vsim16_2024.py` | V500_SIM16 2024 data scan; one-time |
| `check_vsim16_api.py` | One-time API endpoint probe for VSIM16 data |
| `check_vsim16_stats.py` | One-time VSIM16 stats query |
| `compare_months.py` | One-time monthly comparison; superseded by `monthly_stats.py` |
| `debug_api_full.py` | One-time API debugger; one-session use |
| `debug_tm7_db.py` | One-time TM_7 DB debug query; superseded by `compare_tm7_rar.py` |
| `deep_check_files.py` | One-time deep file scan for binary data issues |
| `deep_find_trades.py` | One-time deep trade search; results captured in audit |
| `detect_vsim.py` | One-time VSIM account detection script |
| `detect_vsim_insensitive.py` | Case-insensitive variant of `detect_vsim.py`; redundant |
| `final_api_check.py` | One-time final API health check |
| `find_2024_vsim16.py` | One-time 2024 VSIM16 search |
| `find_all_vsim16.py` | One-time full VSIM16 search across dataset |
| `find_data_accounts.py` | One-time dataset account discovery |
| `find_largest_vsim16.py` | One-time largest VSIM16 file finder |
| `find_trade_txt.py` | One-time `.txt` trade file finder |
| `get_vsim16_symbols.py` | One-time VSIM16 symbol query |
| `get_vsim16_symbols_fixed.py` | Fixed iteration of above; superseded |
| `import_historical_vsim16.py` | One-time VSIM16 historical import trigger |
| `import_historical_vsim16_v2.py` | V2 iteration; import complete, no longer needed |
| `search_large_vsim16.py` | One-time large VSIM16 file scanner |
| `search_vsim16_in_txt.py` | One-time `.txt` VSIM16 search |
| `test_api_sql.py` | Root-level one-time SQL API test; moved to `tests/` pattern |
| `test_db.py` | Root-level one-time DB schema test; covered by `tests/test_database.py` |
| `test_db_filter_2.py` | Second iteration of DB filter test; covered by `tests/test_database.py` |
| `test_db_format.py` | One-time DB output format test |
| `test_matrix_speed.py` | One-time matrix query speed benchmark |
| `test_matrix_speed_2.py` | V2 iteration; results captured; not needed |
| `test_system_raw.py` | One-time raw system API test |
| `test_system_sql.py` | One-time SQL system check |
| `trigger_import.py` | One-time import API trigger; use `scripts/run_full_import.py` instead |
| `verify_jan_mar.py` | One-time Jan-Mar data verification; results captured |

---

## Root-Level Audit Markdown Files: Consolidated into `docs/audits/`

All `*_AUDIT.md` and `*_COMPARISON.md` files at the repository root were moved to `docs/audits/`.
See [`docs/audits/README.md`](file:///c:/SC_results_WF/docs/audits/README.md) for the index and validity status.

| Original Filename | Moved To | Validity Status |
| :--- | :--- | :--- |
| `CLEAN_DATA_SESSION_PNL_AB_COMPARISON.md` | `docs/audits/` | **Superseded** — in-sample only, clean DB comparison |
| `DETAILED_SESSION_PNL_AB_AUDIT.md` | `docs/audits/` | **Superseded** — in-sample only, session PnL detail |
| `FULL_500_DAY_TRADE_COMPARISON_AUDIT.md` | `docs/audits/` | **Historical** — pre-ghost-fix 500-day audit |
| `FULL_562_DAY_STAGE4_PIPELINE_AUDIT.md` | `docs/audits/` | **In-Sample Only** — all 562 days, no OOS split |
| `MASTER_PROJECT_UPDATES_AUDIT.md` | `docs/audits/` | **Historical** — project development timeline |
| `PIPELINE_SUPERIORITY_AUDIT.md` | `docs/audits/` | **In-Sample Only** — Stage 1–4 comparison, full sample |
| `RECOMMENDATION_AB_COMPARISON.md` | `docs/audits/` | **Superseded** — pre-BH-FDR recommendation audit |
| `SESSION_PNL_AB_COMPARISON.md` | `docs/audits/` | **Superseded** — early session PnL A/B test |
| `ULTRA_DETAILED_MASTER_PROJECT_AUDIT.md` | `docs/audits/` | **Historical** — ghost fill fix documentation |
| `VERIFICATION_VS_PROCESSED_COMPARISON.md` | `docs/audits/` | **Valid** — binary parser vs DB field verification |
| `WALK_FORWARD_TEST_AUDIT.md` | `docs/audits/` | **Superseded** — replaced by formal OOS audit |

---

*Last Updated: July 2026 | Repository Audit by Quantitative Engineering Review*
