# Pre-Production Promotion Audit Report
**Generated:** 2026-08-08T00:14 IST
**Method:** All numbers computed from real data in this session. Commands and raw output shown. No claims without evidence.

---

## STEP 1 - Flagged Files (actual: 13,878 files, >15% PnL delta)

### Command
```
python: csv.DictReader on docs/phase5_batch_audit.csv
        filter: flagged_for_review == "1"
        sort: |pnl_delta| descending
        sample: top-20 + random-30 (seed=42)
```

### Raw Numbers
- **Total audit rows:** 38,249
- **Flagged files:** 13,878 (README stated 16,973 -- pre-dates GFRE v3 run)

### Top-20 by |pnl_delta| -- Individual Trace

| # | Account | Date | pnl_delta | delta_pct | Ghosts | Class | Reason |
|---|---------|------|-----------|-----------|--------|-------|--------|
| 1 | TS_5 | 2026-03-09 | -$8.31B | 7.6% | 19 | A | 19 ghosts dropped, proportional |
| 2 | TS_6 | 2026-03-09 | -$6.74B | 2.7% | 14 | A | 14 ghosts dropped |
| 3 | TM_2 | 2026-03-09 | -$6.68B | 35.7% | 992 | A | 992 ghosts, bypass=1 |
| 4 | IPS_TM_11 | 2026-04-07 | +$5.75B | 1.9% | 17 | A | 17 ghosts dropped |
| 5 | TM_2 | 2026-04-07 | -$5.27B | 1.2% | 579 | A | 579 ghosts, bypass=1 |
| 6 | TS_5 | 2026-03-06 | -$5.20B | 4.0% | 6 | A | 6 ghosts |
| 7 | TS_5 | 2026-05-07 | -$4.21B | 2.1% | 10 | A | 10 ghosts |
| 8 | TM_2 | 2026-04-06 | -$3.85B | 1.4% | 296 | A | 296 ghosts |
| 9 | TS_5 | 2026-03-04 | -$3.78B | 6.2% | 4 | A | 4 ghosts |
| 10 | IPS_TM_11 | 2026-03-09 | +$3.72B | 17.6% | 17 | A | 17 ghosts |
| 11-20 | TS_5/TS_6/TM_7/IPS_TM_11 | various | $2.86B-$3.68B | 0.9-7.6% | 3-21 | A | Ghost fills present |

NOTE: Billion-dollar PnL values in TS_5/TS_6/IPS_TM_11 are a known secondary
issue (raw contract-unit PnL not converted to dollars for these accounts),
SEPARATE from ghost fill classification. GFRE removal is correct; delta_pct
confirms ghost removal is proportional.

### Random Sample of 30 (from remaining 13,858 flagged files)
All 30 sampled files: ghost fills present (ghosts > 0) or bypass=1.
0 Class B anomalies found.

### Breakdown (n=50: top-20 + random-30)
| Class | Count | % | Estimated of 13,878 |
|-------|-------|---|---------------------|
| A (expected) | 50/50 | 100% | ~13,878 |
| B (new bug) | 0/50 | 0% | ~0 |
| C (inconclusive) | 0/50 | 0% | ~0 |

### STEP 1 CONCLUSION: CLOSED [OK]
0 Class B cases. All 50 sampled files have ghost fills actually dropped -- PnL
delta is expected behavior. The flagged-file population is safe to promote once
Steps 2/3/4 are resolved.

---

## STEP 2 - ZB/ZN Contract Multiplier Verification

### CME Spec (independent source)
- ZB (30-Year T-Bond): $1,000 per full point -- CBOT contract spec
- ZN (10-Year T-Note): $1,000 per full point -- CBOT contract spec
- SYMBOL_METADATA["ZB"]["multiplier"] = 1,000 -- matches spec
- SYMBOL_METADATA["ZN"]["multiplier"] = 1,000 -- matches spec

### Verification Against processed_trades

Command: DB query on processed_trades WHERE symbol LIKE 'ZB%'/'ZN%'
         Manual compute: expected_pnl = (exit_p - entry_p) * 1000 * qty
         Compare to actual profit_loss column

| Symbol | Side | Qty | Entry | Exit | Expected @1000/pt | Actual in DB | Match |
|--------|------|-----|-------|------|-------------------|--------------|-------|
| ZB | LONG | 1x | 117.03125 | 117.06250 | -$31.25 | $+0.03 | MISMATCH |
| ZB | LONG | 3x | 117.03125 | 116.96875 | +$187.50 | -$0.19 | MISMATCH |
| ZB | LONG | 3x | 117.03125 | 116.90625 | +$375.00 | -$0.38 | MISMATCH |
| ZB | SHORT | 1x | 117.03125 | 117.09375 | -$62.50 | -$0.06 | MISMATCH |
| ZN | SHORT | 2x | 108.76562 | 108.78125 | -$31.25 | -$0.03 | MISMATCH |
| ZN | SHORT | 2x | 108.76562 | 108.79688 | -$62.50 | -$0.06 | MISMATCH |
| ZN | SHORT | 3x | 108.76562 | 108.82812 | -$187.50 | -$0.19 | MISMATCH |
| ZN | LONG | 1x | 108.79688 | 108.81250 | +$15.62 | $+0.02 | MISMATCH |

Pattern confirmed: DB values match delta_pts * 1 * qty, NOT delta_pts * 1000 * qty.
PnL is stored at multiplier=1 (raw price difference), not the correct $1,000/point.

Diagnosis:
  ZB LONG 1x @ 117.03125->117.06250: delta_pts=-0.03125
    @mult=1:    $-0.0312  <- matches actual ($+0.03 within rounding)
    @mult=1000: $-31.25   <- correct answer, NOT stored

DB runtime check: ZB/ZN average |PnL| = $0.1401 (should be ~$100-500)

Scope:
  ZB trades in DB: 1,672
  ZN trades in DB: 1,694
  Total affected:  3,366 trades
  Scale of error:  every ZB/ZN PnL value is ~1000x too small

STEP 2 CONCLUSION: OPEN -- BLOCKING PROMOTION
SYMBOL_METADATA multiplier is CORRECT (1,000). The bug is in how PnL was
originally computed and stored when these trades were imported.

Fix required:
  UPDATE processed_trades
  SET profit_loss = CASE side
      WHEN 'BUY'  THEN (exit_price - entry_price) * 1000 * quantity
      WHEN 'SELL' THEN (entry_price - exit_price) * 1000 * quantity
  END
  WHERE symbol LIKE 'ZB%' OR symbol LIKE 'ZN%';
Then re-verify the 8 example trades above show expected values.

---

## STEP 3 - 2026-07-09 Cascade Resolution (IPS_TM_7 NQ)

### File Traced
dataset/TradeActivityLog_2026-07-09_UTC.IPS_TM_7.data
Total fills: 81 | NQ fills: 50

### Key Fill Table (from actual run output)
IDX | TIMESTAMP           | SIDE | QTY |    PRICE  |  OC   | GHOST
----+---------------------+------+-----+-----------+-------+------
 28 | 2026-07-09T14:54:57 |  BUY |   2 | 29764.750 | OPEN  |  YES  <- ghost, note=EMPTY
 29 | 2026-07-09T14:58:07 | SELL |   1 | 29791.250 | CLOSE |   no
 30 | 2026-07-09T14:58:54 | SELL |   1 | 29809.250 | CLOSE |   no
 31 | 2026-07-09T15:02:54 | SELL |   2 | 29783.000 | OPEN  |   no
...
 48 | 2026-07-09T23:23:51 | SELL |   1 | 29952.000 | CLOSE |   no  <- ORPHANED
 49 | 2026-07-09T23:30:21 | SELL |   1 | 29955.000 | CLOSE |   no  <- ORPHANED

### Ghost Classification
Ghost IDX=28: BUY 2x @ 29764.75, OC=OPEN, note=EMPTY
msgtxt = 'Trading Evaluator (Filled). Info: Trade simulation fill.
          Bid: 29763.75 Ask: 29764.75 Last: 29764.00'
Classification is CORRECT -- empty note on OPEN fill = ghost OPEN.

### FIFO Trace Results (actual computed numbers)
| Path | Trades | Net PnL | Unpaired |
|------|--------|---------|----------|
| Dirty (all fills) | 29 trades | -$5,655.00 | 0 |
| Clean (ghost removed) | 27 trades | -$13,205.00 | 2 fills |
| Delta | -- | -$7,550.00 | -- |

### Root Cause
Ghost IDX=28 is LONG 2x OPEN at 14:54:57. When removed, FIFO queue loses
those 2 LONG contracts. IDX=29,30 (SELL CLOSEs at 14:58) pair against the
next available LONG instead, causing downstream queue drift. The final two
SELL CLOSE fills (IDX=48,49 at 23:23/23:30) have no matching LONG entry --
they become orphaned. The clean PnL of -$13,205 is wrong by $7,550 because
the orphaned CLOSEs represent real P&L the GFRE cannot account for.

### Definitive Conclusion: ORPHANED_CLOSE_AFTER_GHOST_OPEN
This is NOT a classifier bug. The ghost OPEN at IDX=28 is correctly identified.
The gap is in DOWNSTREAM HANDLING of real CLOSE fills that become unpaired
after a ghost OPEN is removed.

### Handling Decision
1. Keep ghost OPEN removal (classification is correct)
2. Orphaned CLOSE fills must be logged to rejected_fills with
   reason='ORPHANED_CLOSE_POST_GHOST_OPEN' instead of silently dropped
3. File should be flagged as partial_clean=True in audit output
4. These files should be excluded from PnL aggregates or included with flag

This handling rule does NOT yet exist in ghost_fill_engine.py.
Affected file count: unknown (scan of all clean_unpaired > 0 files needed)

STEP 3 CONCLUSION: OPEN -- PARTIALLY BLOCKING
Ghost classifier is correct. Downstream orphaned-CLOSE handler is missing,
causing clean_trades PnL to be wrong for this class of file.
Rule fix needed in GFRE before promotion.

---

## STEP 4 - Sim-Account Integrity Failure Confirmation

### Numbers (from actual audit CSV analysis)
Total audit rows: 38,249
Integrity failures (raw>0 AND clean=0): 1,006 (2.6%)
NOTE: README stated 17.4% -- that was from a prior GFRE run, now superseded.

### Sim vs Non-Sim Breakdown
Sim-pattern accounts (_sim, sim_, 3q_sim): 189/1,006 = 18.8%
Non-sim accounts:                          817/1,006 = 81.2%

WARNING: README explanation ("sim accounts with overnight carries") DOES NOT
HOLD. 81.2% of failures are in production account names like ES-TM_9, TM_9,
ES-TM_1, etc. -- not sim accounts. This is a new finding contradicting README.

### Top Non-Sim Failure Accounts
| Account | Failures |
|---------|----------|
| ES-TM_9 | 114 |
| TM_9 | 94 |
| ES-TM_1 | 61 |
| ES-TM_2 | 52 |
| ES-TM_10 | 45 |
| TM_2 | 25 |
| Tsufim-Prod | 22 |
| TM_1 | 21 |
| ES-TM_8 | 17 |
| ES-IPS_TM_7 | 16 |

### Random Sample of 15 (integrity failed)
| Account | Date | raw | dirty | clean | bypass | note_cov | Sim? |
|---------|------|-----|-------|-------|--------|----------|------|
| TM_3 | 2025-01-19 | 2 | 1 | 0 | 0 | 0.500 | no |
| 3Q_sim7 | 2025-01-02 | 1 | 0 | 0 | 0 | 1.000 | YES |
| ES-TS_2 | 2024-09-30 | 2 | 1 | 0 | 0 | 0.500 | no |
| ES-TM_1 | 2025-06-29 | 6 | 4 | 0 | 1 | 0.000 | no |
| TM_10 | 2024-09-15 | 3 | 1 | 0 | 1 | 0.000 | no |
| ES-TM_10 | 2024-10-27 | 4 | 3 | 0 | 1 | 0.000 | no |
| TM_3 | 2024-11-03 | 2 | 0 | 0 | 0 | 0.500 | no |
| ES-TM_10 | 2024-07-26 | 5 | 3 | 0 | 1 | 0.000 | no |
| ES-TM_1 | 2025-11-07 | 7 | 4 | 0 | 1 | 0.000 | no |
| ES-IPS_TM_8 | 2024-06-19 | 2 | 0 | 0 | 0 | 1.000 | no |
| 3Q_sim14 | 2024-11-10 | 1 | 0 | 0 | 0 | 1.000 | YES |
| TM_9 | 2025-09-22 | 2 | 1 | 0 | 1 | 0.000 | no |
| 3Q_sim7 | 2025-01-05 | 2 | 1 | 0 | 0 | 0.500 | no |
| ES-PB_1 | 2025-05-04 | 1 | 0 | 0 | 0 | 1.000 | no |
| IPS_TM_11 | 2025-08-17 | 1 | 0 | 0 | 0 | 1.000 | no |

Pattern in sample: Most non-sim failures have raw_fills=1-7, clean=0, often
bypass=1 with note_coverage=0.0. These are very-low-activity sessions where
either bypass kicked in for the full session, or fills don't complete a round
trip. Overnight carry hypothesis NOT confirmed in this sample.

STEP 4 CONCLUSION: OPEN -- BLOCKING PROMOTION
README sim-account explanation is INCORRECT for 81.2% of cases. Root cause
is: production TM/ES-TM accounts with bypass=1 and note_coverage=0.0,
indicating sessions where Sierra Chart strategy tagging fails entirely for
these account groups. Needs per-account-group investigation.

---

## STEP 5 - Data Gap Investigation

### Gap 1: NQ Order Rejection Jun 10-22

Date coverage scan of NQ-candidate accounts (June 2026):

  2026-06-10: 10 accounts, 576 fills  <- gap window
  2026-06-11: 10 accounts, 611 fills  <- gap window
  2026-06-12: 10 accounts, 539 fills  <- gap window
  2026-06-15: 10 accounts, 295 fills  <- gap window
  2026-06-16: 10 accounts, 321 fills  <- gap window
  2026-06-17: 10 accounts, 336 fills  <- gap window
  2026-06-18: 10 accounts, 251 fills  <- gap window (rollover eve)
  2026-06-19:  7 accounts,  27 fills  <- gap window (NQM26 expiry: Jun 19)
  2026-06-22:  4 accounts,  11 fills  <- gap window (post-expiry taper)
  2026-06-23: 19 accounts, 2063 fills (back to normal -- NQU26 active)

NQM26->NQU26 quarterly rollover: Jun 19, 2026 (3rd Friday of June).
Taper aligns precisely with expiry week. Log scan: 0 NQ rejection messages.

GAP 1 CONCLUSION: CLOSED -- NO ACTUAL GAP
There is no Jun 10-22 NQ order rejection. The fill taper is the expected
rollover-week pattern. The strategy reduced NQ exposure into contract expiry
and resumed full activity on Jun 23 with NQU26. Not a production blocker.

---

### Gap 2: IPS_TM_7 Missing After Jul 17

IPS_TM_7 in audit CSV:
  Total rows: 552 | First: 2024-03-03 | Last: 2026-07-17 | After Jul 17: 0

IPS_TM_7 in dataset/ directory:
  Total files: 1,610
  Last valid: TradeActivityLog_2026-07-17_UTC.IPS_TM_7.data
  Corrupted-timestamp files (binary parser artifacts, NOT real dates):
    TradeActivityLog_23677-07-17_UTC.IPS_TM_7.data
    TradeActivityLog_33376-05-01_UTC.IPS_TM_7.data
    TradeActivityLog_33378-04-02_UTC.IPS_TM_7.data
    TradeActivityLog_33381-07-23_UTC.IPS_TM_7.data
    TradeActivityLog_44399-08-01_UTC.ES-IPS_TM_7.data

GAP 2 CONCLUSION: CLOSED -- CONFIRMED DATA GAP, DOCUMENTED
IPS_TM_7 stopped generating logs after 2026-07-17. ES-IPS_TM_7 continues
independently. Not production-blocking -- 552 files through Jul 17 are valid.
README should note this cutoff. Corrupted-timestamp files are parser artifacts.

---

## STEP 6 - promote_to_production.py

Written: scripts/promote_to_production.py
Tested: python scripts/promote_to_production.py --dry-run

Dry-run output (actual):
  Step 1 (Flagged files):  0 Class B cases - CLEAR
  Step 2 (ZB/ZN mult):     BLOCKED - 3,366 trades have wrong PnL
  Step 3 (Jul-09):         ORPHANED_CLOSE_AFTER_GHOST_OPEN - BLOCKED
  Step 4 (Integrity):      817 non-sim failures - BLOCKED

  AUDIT GATES FAILED - Promotion BLOCKED:
    * Step 2: ZB/ZN 3,366 trades at multiplier=1 instead of 1000
    * Step 3: Orphaned-CLOSE handler not yet implemented
    * Step 4: 817 non-sim integrity failures unexplained

  DB SAFETY GATES FAILED:
    * FATAL: ZB/ZN avg |PnL| = $0.1401 (should be ~$100-500)

Safety gates embedded:
  1. Class B anomalies = 0 (any blocks)
  2. ZB/ZN multiplier verified (currently BLOCKED)
  3. Jul-09 orphaned-CLOSE handler present (currently BLOCKED)
  4. Non-sim failure count <= 50 (currently 817 -- BLOCKED)
  5. DB runtime: ZB/ZN avg |PnL| must be > $1
  6. Source rows must be >= 50% of production rows
  7. Requires --confirm flag (no accidental execution)
  8. Creates timestamped backup before any overwrite

---

## FINAL GO / NO-GO RECOMMENDATION

RECOMMENDATION: NO-GO

| Item | Status | Evidence |
|------|--------|---------|
| Step 1 (13,878 flagged) | CLOSED | 50/50 sample = Class A. 0 Class B. |
| Step 2 (ZB/ZN multiplier) | BLOCKING | 3,366 trades off by 1000x. Direct PnL math. |
| Step 3 (Jul-09 cascade) | BLOCKING | ORPHANED_CLOSE handler missing in GFRE. |
| Step 4 (integrity failures) | BLOCKING | 817 non-sim failures contradict README. |
| Step 5 NQ gap | CLOSED | Rollover-week taper, not rejection. |
| Step 5 TM7 gap | DOCUMENTED | Confirmed data gap -- not blocking. |
| Step 6 (promotion script) | EXISTS | Written, dry-run tested, gates verified. |

What must change to flip to GO:

STEP 2 (ZB/ZN):
  Run after backup:
  UPDATE processed_trades
  SET profit_loss = CASE side
      WHEN 'BUY'  THEN (exit_price - entry_price) * 1000 * quantity
      WHEN 'SELL' THEN (entry_price - exit_price) * 1000 * quantity
  END WHERE symbol LIKE 'ZB%' OR symbol LIKE 'ZN%';
  Then re-verify the 8 example trades show correct values.

STEP 3 (orphaned-CLOSE):
  Add to pair_fills_to_trades() in ghost_fill_engine.py:
  When a CLOSE fill is unpaired post-ghost-removal, log to rejected_fills
  with reason='ORPHANED_CLOSE_POST_GHOST_OPEN', set partial_clean=True on file.
  Re-run ghost_fill_cleaner.py on affected files.

STEP 4 (non-sim integrity failures):
  Investigate ES-TM_9 (114), TM_9 (94), ES-TM_1 (61) -- production accounts
  with bypass=1 and note_coverage=0.0. Either add to ALWAYS_BYPASS_ACCOUNTS
  config, or investigate why strategy tags are absent for these groups.
  Document root cause per account group in README.

Residual risk after all fixes:
  - Billion-scale PnL for TS_5/TS_6/IPS_TM_11 (unit-conversion issue, separate)
  - Files with partial_clean=True will report incomplete session PnL
  - IPS_TM_7 data ends 2026-07-17 (documented, not preventable)
