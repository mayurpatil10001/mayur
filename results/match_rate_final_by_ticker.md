# Match-Rate Verification - All Accounts x All Base Symbols

**Generated:** 2026-09-18 23:25  
**Method:** DB-centric price-only match (4 workers, checkpointed)  
**Price tolerance:** +/-0.5 on entry_price  
**Day window:** +/-1 calendar day  
**Timestamp:** NOT used (SC ts_val local wall-clock != DB timezone)  
**Files parsed:** 54,500 of 64,397 (DB-account-filtered)  
**PASS:** >=95.0%  **WARN:** >=90.0%  **FAIL:** <90.0%  

## Per-Ticker Summary

| Symbol | Combos | DB Trades | Matched | No-Log | Unmatched | Match% | Status |
|--------|-------:|----------:|--------:|-------:|----------:|-------:|--------|
| CL | 45 | 225,308 | 225,308 | 0 | 0 | 100.00% | **PASS** |
| ES | 35 | 1,728,605 | 1,728,605 | 0 | 0 | 100.00% | **PASS** |
| FDAX | 29 | 338,003 | 338,003 | 0 | 0 | 100.00% | **PASS** |
| MES | 1 | 6 | 6 | 0 | 0 | 100.00% | **PASS** |
| MNQ | 2 | 119 | 119 | 0 | 0 | 100.00% | **PASS** |
| NQ | 74 | 615,023 | 615,023 | 0 | 0 | 100.00% | **PASS** |
| ZB | 28 | 6,472 | 6,472 | 0 | 0 | 100.00% | **PASS** |
| ZN | 28 | 5,875 | 5,875 | 0 | 0 | 100.00% | **PASS** |

> **Blended (cross-symbol, NOT headline):** 2,919,411/2,919,411 = 100.00%

## Methodology

- **Direction:** DB-centric: for each DB trade, find matching log fill by price
- **Price match:** |fill_price - entry_price| <= 0.5
- **Day window:** +/-1 calendar day from DB entry_date
- **No-Log:** DB trades where log has zero fills for that account/date
- **Unmatched:** log fills present but no price within +/-0.5
- **Parallelism:** multiprocessing.Pool with module-injection bypass (no scipy OOM)
- **Checkpointing:** log_index saved to pickle every 10k files; resumable on restart
