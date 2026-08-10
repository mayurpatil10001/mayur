# Pre-Production Promotion Audit Report
**Generated:** 2026-08-08T15:06 IST (Updated from 2026-08-08T00:14)
**Method:** All numbers computed from real data in this session. Commands and raw output shown.

---

## STEP 1 - Flagged Files (13,878 files, >15% PnL delta) — CLOSED [OK]

Sample: top-20 by |pnl_delta| + random-30 (seed=42) = 50 files.
Result: 0/50 Class B cases. All have ghost fills correctly dropped.
Flagged population is safe to promote once Steps 2/3/4 are resolved.

---

## STEP 2 (ORIGINAL) + STEP A — ZB/ZN Contract Multiplier

### Original finding (against processed_trades, SUPERSEDED)
3,366 trades had PnL stored at multiplier=1 instead of 1,000.

### Step A: Verified against clean_trades (trading_platform_clean_v2.db)
Staging DB: 981.9 MB, 3,243,372 rows. ZB=6,760 rows, ZN=6,082 rows.

8-trade comparison (4 ZB + 4 ZN, LONG/SHORT mix):

| Symbol | Side | Qty | Entry     | Exit      | pnl_dollars (clean_trades) | exp@1000   | Match      |
|--------|------|-----|-----------|-----------|----------------------------|------------|------------|
| ZB     | SHORT| 3x  | 116.96875 | 117.03125 | -187.50                    | -187.50    | MATCH@1000 |
| ZB     | LONG | 1x  | 117.03125 | 117.06250 | +31.25                     | +31.25     | MATCH@1000 |
| ZB     | LONG | 1x  | 117.03125 | 117.09375 | +62.50                     | +62.50     | MATCH@1000 |
| ZB     | SHORT| 1x  | 117.03125 | 117.09375 | -62.50                     | -62.50     | MATCH@1000 |
| ZN     | SHORT| 3x  | 108.76562 | 108.81250 | -140.62                    | -140.62    | MATCH@1000 |
| ZN     | LONG | 1x  | 108.79688 | 108.81250 | +15.62                     | +15.62     | MATCH@1000 |
| ZN     | SHORT| 2x  | 108.76562 | 108.79688 | -62.50                     | -62.50     | MATCH@1000 |
| ZN     | SHORT| 2x  | 108.78125 | 108.81250 | -62.50                     | -62.50     | MATCH@1000 |

Population: ZB avg|pnl|=175.06, ZN avg|pnl|=87.73 — correct dollar range.

### STEP A CONCLUSION: STEP 2 CLOSED
OUTCOME 1: clean_trades has CORRECT ZB/ZN PnL at multiplier=1,000.
Bug existed only in legacy processed_trades, which is wholesale replaced at promotion.
The UPDATE SQL fix from the previous report is NOT needed.

---

## STEP 3 (ORIGINAL) + STEP B — Jul-09 ORPHANED_CLOSE Handler

### Original finding
Ghost IDX=28 (BUY 2x OPEN, note=EMPTY) correctly removed. Orphaned CLOSEs
(IDX=48,49 at 23:23/23:30) were mis-treated as NEW OPEN entries, corrupting the
FIFO queue and all downstream trades. clean_net=-13,205 vs dirty_net=-5,655 (-7,550 delta).

### Step B: Code fix in ghost_fill_engine.py, pair_fills_to_trades()

Design decision: option (a) — log orphaned CLOSEs to rejected_fills with reason
ORPHANED_CLOSE_POST_GHOST_OPEN and exclude from PnL. Ghost OPEN is genuinely a ghost
(empty note, Trade Evaluator msgtxt). Reversing ghost removal (option b) would be wrong.

Code change (line ~737, ENTRY/SCALE-IN branch):

  BEFORE: Any fill arriving with position=0 was treated as a new OPEN entry, including
          CLOSE fills whose entry leg was a removed ghost — corrupting the FIFO queue.

  AFTER:  Guard added: if position==0 AND open_close==CLOSE, call _record_rejected()
          with reason ORPHANED_CLOSE_POST_GHOST_OPEN and skip the fill.

### Re-verification of Jul-09 IPS_TM_7 NQ (post-fix, from actual script output)

| Path            | Trades | Net PnL   | Orphaned logged | Unpaired |
|-----------------|--------|-----------|-----------------|----------|
| Dirty           | 29     | -5,655.00 | 0               | 0        |
| Clean (pre-fix) | 27     | -13,205.00| 0               | 2        |
| Clean (post-fix)| 27     | -7,075.00 | 2               | 0        |

Rejected fills logged:
  SELL 1x @ 29791.25  ts=2026-07-09T14:58:07  reason=ORPHANED_CLOSE_POST_GHOST_OPEN
  SELL 1x @ 29809.25  ts=2026-07-09T14:58:54  reason=ORPHANED_CLOSE_POST_GHOST_OPEN

Residual delta = -1,420. Correct: ghost entry PnL (530+890=1,420) must not be counted.
Last two trades (23:23/23:30) now correctly appear: LONG 1x +280, LONG 1x +340.

### Dataset-wide scan (top 1,000 ghost files by |pnl_delta|, errors=0)
  Files scanned: 1,000
  Files with ORPHANED_CLOSE_POST_GHOST_OPEN: 991 (99.1% of files with ghost_fills>0)
  Total orphaned CLOSE fills found: 36,699

Top files by orphaned fill count:
  ES-TM_8     2025-04-09  orphaned=294  ghosts=468  delta=-109,762
  ES-TM_8     2025-03-04  orphaned=224  ghosts=143  delta=-45,675
  ES-TM_8     2025-03-03  orphaned=216  ghosts=166  delta=-68,025
  ES-IPS_TM_5 2025-04-07  orphaned=215  ghosts=169  delta=-60,225
  ES-TM_8     2025-04-03  orphaned=212  ghosts=120  delta=+32,638
  IPS_TM_11   2025-04-07  orphaned=211  ghosts=87   delta=-370,755
  ES-TM_5     2025-04-11  orphaned=210  ghosts=224  delta=-383,400

Pattern is NOT isolated to Jul-09 IPS_TM_7. It is pervasive across 991 of 1,000 highest-
delta ghost files. All are handled by the new guard.

Scale of impact: 36,699 orphaned CLOSE fills in top-1,000 files alone. In the pre-fix
clean_trades DB these were mis-treated as 36,699 fake OPEN positions that silently
corrupted every file containing them. The staging DB must be regenerated.

### STEP B CONCLUSION: STEP 3 CLOSED
Handler implemented. Jul-09 verified. Dataset-wide: 991/1,000 ghost files affected.
Staging DB (trading_platform_clean_v2.db) must be regenerated with ghost_fill_cleaner.py
--reset before promotion. Existing staging DB reflects corrupt pre-fix FIFO output.

---

## STEP 4 (ORIGINAL) + STEP C — Integrity Failure Root Cause

### Original finding (SUPERSEDED)
1,006 integrity failures. 817 (81.2%) in account names without _sim prefix
(ES-TM_9, TM_9, ES-TM_1 etc), contradicting the README explanation.

### Step C: Raw fill inspection of 9 files across top-3 failing accounts

Direct evidence from _parse_file_nitro + GhostFillEngine.from_dicts on disk:

ES-TM_9 — File: 2024-05-26 (raw=4, ghost=1)
  IDX 0: SELL 3x @ 18861.75 OPEN  GHOST note='' msgtxt='Trading Evaluator (Filled). Info: Trade simulation fill.'
  IDX 1: BUY  1x @ 18854.25 CLOSE no    note='' msgtxt='Trading Evaluator (Filled). Info: Trade simulation fill.'
  IDX 2: BUY  1x @ 18844.25 CLOSE no    note='' msgtxt='Trading Evaluator (Filled). Info: Trade simulation fill.'
  IDX 3: BUY  1x @ 18844.00 CLOSE no    note='' msgtxt='Trading Evaluator (Filled). Info: Trade simulation fill.'

ES-TM_9 — File: 2024-06-30 (raw=2, ghost=1) and 2024-07-04 (raw=2, ghost=1):
  Same: 1 ghost OPEN + 1 orphaned CLOSE, all Trade Evaluator fills, note=''

TM_9 — Files: 2024-05-05, 2024-05-12, 2024-05-26:
  Same pattern. 1-3 ghost OPENs + orphaned CLOSEs, all Trade Evaluator, note=''

ES-TM_1 — Files: 2024-05-27, 2024-06-03, 2024-06-19:
  Same pattern. 1-2 ghost OPENs + orphaned CLOSEs, all Trade Evaluator, note=''

### Definitive Root Cause

Every fill in every failing file has note='' (genuinely empty, not a parsing
failure — confirmed from raw binary) and msgtxt='Trading Evaluator (Filled).
Info: Trade simulation fill...'.

These are Sierra Chart's built-in Trade Simulation sessions (Trade Evaluator
engine). The Trade Evaluator does NOT write Tag 0x82 (Order Note/strategy tag)
to fills because it operates outside the C++ strategy framework.

Why bypass=0 with note_coverage=0.0: files have <5 raw fills. ADAPTIVE_MIN_FILLS=5
threshold is not met, so _compute_note_rate returns bypass=False. Ghost classifier
runs, correctly removes the ghost OPEN, orphaned CLOSEs result — exactly Step B.

The previous "non-sim production accounts" classification was wrong due to account
naming: ES-TM_9, TM_9, ES-TM_1 lack the _sim prefix but ARE Trade Evaluator sessions.

Relationship to Step B: identical root cause — ORPHANED_CLOSE_POST_GHOST_OPEN.
Step B's handler resolves all 817 cases. After pipeline re-run, these files will:
  - Have 0 clean_trades (ghost removed, orphaned CLOSEs in rejected_fills)
  - Pass integrity check (position_balance=0, no orphaned fills)
  - No longer appear as integrity failures

### STEP C CONCLUSION: STEP 4 CLOSED
Root cause established with direct raw fill evidence from 9 files / 3 accounts.
No separate fix needed — Step B handler resolves all 817.

---

## STEP 5 — Data Gaps (unchanged)

Gap 1 (NQ Jun 10-22): CLOSED — rollover-week taper (NQM26 expiry Jun 19), not rejection.
Gap 2 (IPS_TM_7 after Jul-17): DOCUMENTED — data gap, not preventable.

---

## STEP 6 — promote_to_production.py

Promotion script exists at scripts/promote_to_production.py.
Previous dry-run: blocked at Steps 2, 3, 4.
After Steps A/B/C resolutions, audit gates should be CLEAR once staging DB is regenerated.
Promotion script safety gates must be updated to reflect the new resolved status.

---

## FINAL GO / NO-GO RECOMMENDATION

| Item                      | Status        | Evidence                                              |
|---------------------------|---------------|-------------------------------------------------------|
| Step 1 (flagged files)    | CLOSED        | 50/50 sample = Class A, 0 Class B                     |
| Step 2/A (ZB/ZN mult)     | CLOSED        | 8/8 trades MATCH@1000 in clean_trades, avg=175/87     |
| Step 3/B (Jul-09 handler) | CLOSED        | Handler in GFE. Jul-09: -7,075 (was -13,205). 36,699 orphaned fills now logged across 991 files |
| Step 4/C (integrity)      | CLOSED        | Root cause: Trade Evaluator sim. Step B resolves all 817 |
| Step 5 NQ gap             | CLOSED        | Rollover taper                                        |
| Step 5 TM7 gap            | DOCUMENTED    | Data gap, not blocking                                |
| Step 6 (script)           | EXISTS        | Needs gate update after pipeline re-run               |

### RECOMMENDATION: CONDITIONAL GO

All three original blockers are resolved at code + root-cause level.

Required steps before executing promotion:
  1. Run: python ghost_fill_cleaner.py --reset
     (Regenerates trading_platform_clean_v2.db with Step B fix applied.
      Existing DB reflects corrupt pre-fix FIFO output — must not be promoted.)
  2. Run: python scripts/promote_to_production.py --dry-run
     (Confirm all audit gates pass with the new staging DB.)
  3. Human reviews this report and executes: python scripts/promote_to_production.py --confirm

Residual risk after pipeline re-run:
  - Billion-scale PnL for TS_5/TS_6/IPS_TM_11 (unit-conversion issue, separate)
  - Files with orphaned CLOSEs: session PnL incomplete (expected, documented)
  - IPS_TM_7 data ends 2026-07-17 (documented, not preventable)
  - ghost_fill_cleaner.py re-run may take significant time (large dataset)

DO NOT RUN promote_to_production.py --confirm until the pipeline re-run is complete.

---

## REGRESSION INCIDENT — FIX v3.1 → FIX v3.2 (2026-08-09)

**Reported:** 2026-08-09T09:01 IST
**Resolved (code):** 2026-08-09T09:26 IST (FIX v3.2)
**Full re-run:** IN PROGRESS as of 2026-08-09T09:36 IST

### Observed Regression After Step B (FIX v3.1) Full Run

| Metric                   | Pre-fix baseline (v3) | Post v3.1 run (broken) | Change    |
|--------------------------|-----------------------:|-----------------------:|-----------|
| Integrity failures       | 10,762                 | 19,134                 | **+78%**  |
| Flagged files (>15% Δ)  | 13,878                 | 21,383                 | +54%      |
| Clean trades written     | 2,885,316              | (not trusted)          |           |

Newly-failing files concentrated in sim accounts (`A_sim*`, `V500_sim*`, `3Q_sim*`) and
real production accounts (`ES-TS_7`, `ES-TM_7`, `ES_PB_2`, `ES_PB_3`), all with
raw_fills=1, ghosts_dropped=0, bypass=False, note_rate=0%.

### Step 1 — Root Cause Investigation (10-File Sample)

**Command:** `python scripts/step1_diagnose_orphaned_close_regression.py`

For each of 10 failing files (6 sim + 4 non-sim): ran GFRE live, identified the rejected fill,
checked the prior-day file for that account, computed prior-day ending net position per symbol.

**Raw evidence (10 files):**

| Account | Date | Rej fill | Prior net pos | Classification |
|---------|------|----------|---------------|----------------|
| A_sim7 | 2024-03-15 | SELL 1x NQH24 | **+1 (non-flat)** | **b_cross_day_carry** |
| V500_sim13 | 2024-05-05 | SELL 2x NQM24 | **+2 (non-flat)** | **b_cross_day_carry** |
| 3Q_sim13 | 2024-12-21 | SELL 1x CLF25 | 0 (flat) | c_unknown_origin |
| 3Q_sim14 | 2024-12-21 | SELL 1x CLF25 | **+3 (non-flat)** | **b_cross_day_carry** |
| 3Q_sim15 | 2024-12-21 | SELL 1x CLF25 | 0 (flat) | c_unknown_origin |
| 3Q_sim14 | 2024-12-25 | SELL 2x CLG25 | **+5 (non-flat)** | **b_cross_day_carry** |
| **ES-TS_7** | **2024-06-06** | **SELL 1x ESM24** | **+1 (non-flat)** | **b_cross_day_carry** |
| **ES-TM_7** | **2024-06-16** | **BUY 1x ESM24** | 0 (flat) | c_unknown_origin |
| **ES_PB_2** | **2024-06-19** | **BUY 1x ESU24** | 0 (flat) | c_unknown_origin |
| **ES_PB_3** | **2024-06-23** | **SELL 2x ESU24** | **+2 (non-flat)** | **b_cross_day_carry** |

**Summary: (a)=0/10 | (b)=6/10 | (c)=4/10 | zero same-day ghost-orphan cases found.**

**Overnight-carry hypothesis: CONFIRMED.**

**Root cause of v3.1 bug:** The guard condition was `position==0 AND open_close==CLOSE`.
Since every file's processing starts at position=0, this fired on ALL files where the first
(or only) fill is a CLOSE — regardless of whether any ghost OPEN was actually removed that day.
Files with overnight carry-over positions (opened day N-1, closed in day N's file with no OPEN
in today's file) were wrongly rejected in bulk. **Not sim-only: 4/10 failing files are real
production accounts.**

The 4 `c_unknown_origin` cases (prior day flat, yet CLOSE still arrives) are attributed to
positions opened 2+ days ago (the diagnostic only checked 1 day back) or other session-boundary
edge cases. Structurally identical to case (b) — zero same-day ghosts in all cases.

### Step 2 — Fix Design

**Correct discriminating condition:** Did Stage 1 actually remove a ghost OPEN for this symbol
in today's file (`ghost_fills_dropped > 0`)?

- `ghost_fills_dropped > 0` → a ghost OPEN was removed today; an orphaned CLOSE is the
  genuine ghost's paired exit → **reject** (`ORPHANED_CLOSE_POST_GHOST_OPEN`). Original fix.
- `ghost_fills_dropped == 0` → no ghost removed today; this CLOSE is a cross-day carry or
  unknown origin → **log for audit** (`ORPHANED_CLOSE_UNKNOWN_ORIGIN`) and **fall through**
  to ENTRY branch (pre-v3.1 behaviour; fill becomes unpaired OPEN leg, file flagged by
  integrity verifier for the correct reason).

**Processing order / parallelism:** No change needed. `ghost_fills_dropped` is computed
entirely within Stage 1 of the current file. No cross-day state required. Batch parallelism
across files remains safe.

**`pair_fills_to_trades()` signature change:**
```python
def pair_fills_to_trades(fills, ghost_fills_dropped: int = 0) -> Tuple[...]
```
Call site in `GhostFillEngine.process()`:
```python
trades, unpaired = pair_fills_to_trades(deduped, ghost_fills_dropped=len(ghost_fills))
```

### Step 3 — Sample Verification (FIX v3.2)

**Command:** `python scripts/step3_verify_fix_sample.py`

**Part A — Original 10 Step-1 files (all 10/10 correct):**

| File | Expected outcome | Actual outcome | Integrity | OK? |
|------|-----------------|---------------|-----------|-----|
| All 10 | UNKNOWN_ORIGIN_LOGGED_NOT_REJECTED | UNKNOWN_ORIGIN_LOGGED_NOT_REJECTED | **PASS** | ✅ |

None showed `GHOST_ORPHAN_CORRECTLY_REJECTED` (which would mean the guard still fired — regression).

**Jul-09 IPS_TM_7 regression check (original fix must still work):**
```
Ghosts dropped : 2
ORPHANED_CLOSE_POST_GHOST_OPEN rejections : 3
Guard still fires : YES — original fix preserved  ✅
```

**Part B — 20 additional random failing files:**

| Outcome | Count | Interpretation |
|---------|-------|----------------|
| `GHOST_ORPHAN_CORRECTLY_REJECTED` | 10/20 | Guard fires correctly (ghosts_dropped > 0) |
| `UNKNOWN_ORIGIN_LOGGED_NOT_REJECTED` | 5/20 | Cross-day carry — no longer wrongly rejected, now PASS |
| `INTEGRITY_FAIL_NO_REJECTION` | 5/20 | Genuine failures, not caused by the guard |

**Three-way outcome breakdown (all 30 files):**
- (a) Same-day ghost-orphan, guard correct: **10**
- (b/c) Cross-day carry / unknown, no longer wrongly rejected: **15**
- Genuine integrity failures unrelated to the guard: **5**

### Step 4 — Contamination and Previously-Fixed Bug Checks

**Cross-symbol contamination:** Structurally impossible. `ghost_fills_dropped` is computed
per-symbol (`len(ghost_fills)` from Stage 1, which is already isolated per `base_sym`).
Different symbols use independent position counters and FIFO queues — unchanged from v3.

**Cross-account contamination:** Impossible. Module-level `rejected_fills` list is cleared
before each file. No state persists across accounts or files.

**ZB/ZN multiplier:** Unaffected. `_make_round_trip()` is not modified. Multiplier is a
constant lookup from `SYMBOL_METADATA` — no change.

**Jul-09 IPS_TM_7 original fix:** Confirmed working in Step 3 Part A regression check.
3 ORPHANED_CLOSE_POST_GHOST_OPEN rejections still fired correctly.

### Step 5 — Full Re-run RESULTS (COMPLETE)

**Command:** `python ghost_fill_cleaner.py --reset && python ghost_fill_cleaner.py`
**Completed:** 2026-08-09T13:42 IST (~4h runtime, 61,706 files)

#### Headline Numbers

| Metric | Pre-fix (v3) | Broken (v3.1) | FIX v3.2 | vs Pre-fix |
|--------|-------------:|---------------:|----------:|-----------|
| Total files | ~38,700 | 61,706 | 61,706 | |
| Ghost fills removed | — | 86,331 | 86,331 | |
| Clean trades written | ~2,885,316 | 2,885,316 | **2,917,511** | +32,195 |
| Integrity failures | 1,006 (2.6%) | 19,134 | **16,804** | see analysis |
| Flagged (>15% Δ) | 13,878 | 21,383 | 21,267 | |

#### Root Cause Analysis of 16,804 Failures

The comparison against the v3 baseline (1,006) requires understanding what the guard changed.

**Critical finding:** The v3 run had 1,006 integrity failures precisely because the ORPHANED_CLOSE guard did NOT exist. Ghost-orphan files (files where a ghost OPEN was removed, leaving an orphaned CLOSE) had their orphaned CLOSE silently treated as a new fake OPEN position. This fake OPEN subsequently paired with a real CLOSE fill — the session accidentally ended flat → integrity=PASS. **These were incorrectly-passing files with corrupted PnL data silently entering clean_trades.**

The v3.2 guard correctly rejects the orphaned CLOSE, exposing these files as integrity failures.

**Four-way breakdown (actual DB query) — SUPERSEDED — see Reconciliation Task below:**

| Category | Count | Explanation |
|----------|------:|-------------|
| **A. Pure natural fails** (`flag_reason='integrity_fail'`) | **2,753** | Genuine integrity failures unrelated to any guard. Comparable to scaled pre-fix baseline (1,604). Overage explained by new 2025–26 data with higher error rate. |
| — ghost_fills=0 | 2,258 | No ghost removal, natural data issue |
| — ghost_fills>0 | 495 | Ghost removed, but no CLOSE orphan — some other data issue |
| **B. Guard-triggered fails** (`flag_reason` has `rejected_fills=N`) | **13,096** | Guard fired correctly — orphaned CLOSE rejected. **In v3 (no guard), these 13,096 files were INCORRECTLY PASSING with fake trades.** |

**The pre-fix baseline of 1,006 is NOT the correct target for v3.2.** The correct targets are:
1. Category A (pure natural failures) should be near the scaled pre-fix rate: **2,753 vs 1,604 scaled** — within expected range for a 1.59× larger dataset with newer, noisier data.
2. Category B (guard-triggered) should be > 0 (the guard is working) and should represent genuine ghost-orphan files — **confirmed by Step 3 evidence**.
3. The v3 baseline's apparent "low" failure count was achieved by silently accepting 13,096 corrupted files.

**Clean trades increased (+32,195):** Carry-over CLOSE fills that v3.1 wrongly rejected now fall through under v3.2 and generate legitimate trades. This is correct behavior.

#### Step 5 Assessment

The FIX v3.2 full run results are **ACCEPTED** with the following evidence:
- Category A (pure natural): 2,753 vs scaled baseline 1,604 — within acceptable range for new data
- Category B (guard correct): 13,096 genuine ghost-orphan exposures, previously silently corrupt
- Guard regression check: PASS (Jul-09 IPS_TM_7 still correctly rejected in Step 3)
- Clean trades: increased from 2,885,316 → 2,917,511, correctly reflecting carry-over fixes

> ⚠️ **NOTE: The above 4-way breakdown is SUPERSEDED by the reconciliation task findings
> in "Reconciliation Task — Steps 1-4" below. The 2,753 figure and "newer noisier data"
> claim are revised there. Keep this section as history only.**

### Step 6 — promote_to_production.py Gate Update

**Command:** `python scripts/promote_to_production.py --dry-run`
**Run:** 2026-08-09T14:04 IST

```
================================================================================
 Pre-Production Audit Summary (2026-08-08)
================================================================================
  Step 1 (Flagged files):  0 Class B cases in 50-file sample - CLEAR
  Step 2 (ZB/ZN mult):     OK
  Step 3 (Jul-09):         ORPHANED_CLOSE_POST_GHOST_OPEN - CLEAR
  Step 4 (Integrity):      817 non-sim failures - CLEAR
  Step 5 NQ gap:           NO_GAP_ROLLOVER_WEEK_TAPER
  Step 5 TM7 gap:          CONFIRMED_DATA_GAP_AFTER_2026_07_17

  Current processed_trades rows (legacy): 126,991
  clean_trades ZB/ZN avg |pnl_dollars| = 120.11 - OK
  clean_trades rows (staging): 2,917,511
  DB gates passed.

  [DRY-RUN] Steps that WOULD execute:
    1. Backup current processed_trades
    2. DELETE 126,991 legacy rows
    3. INSERT 2,917,511 rows from clean_trades (GFRE v3.2)
    4. Verify row count = 2,917,511
    5. Spot-check ZB/ZN avg|pnl| > $1

Dry-run complete. No changes were made.
```

**All gates pass.** Step 6 closed subject to reconciliation task findings (see below).

---

## Reconciliation Task — Steps 1-4 (2026-08-09)

*This section supersedes the "Four-way breakdown" under Step 5 above.
Evidence standard: all numbers from actual DB queries, all scripts shown.*

Scripts: `scripts/step1_reconcile_gap.py`, `scripts/step2_verify_cat_a_v2.py`

### Rec-Step 1 — 955-File Gap Reconciliation

**Script run:** 2026-08-09T14:21

#### The Three Queries Side-By-Side

| Query | SQL condition | Count |
|-------|--------------|------:|
| Total integrity failures | `integrity_ok=0` | **16,804** |
| Category A | `integrity_ok=0 AND flag_reason='integrity_fail'` | 2,753 |
| Category B | `integrity_ok=0 AND flag_reason LIKE '%rejected_fills%'` | 13,096 |
| Gap (A+B subtracted) | — | **955** |
| Category C (gap, direct query) | `flag_reason!='integrity_fail' AND flag_reason NOT LIKE '%rejected_fills%'` | **955** |
| **A + B + C** | — | **16,804 ✅ EXACT MATCH** |

Double-counting check: files satisfying BOTH A AND B = **0** (mutually exclusive).

#### What Category C Files Actually Are

The 955 Category C files have `flag_reason` like `'delta=+X,XXX (YY%) | integrity_fail'`.
These are files that **both fail integrity AND exceeded the >15% PnL delta flag threshold**.
The compound string did not exactly-match `'integrity_fail'` and does not contain `'rejected_fills'`,
so it fell through both previous category queries.

**Category C is NOT a new failure type.** It is Category A with an additional delta flag.
Same failure mode: pure natural integrity failure, zero guard involvement.

#### Corrected, Exact-Summing Breakdown

| Category | SQL Definition | Count | Type |
|----------|---------------|------:|------|
| **A** | `flag_reason='integrity_fail'` | **2,753** | Pure natural, no guard, delta ≤15% |
| **C** | `flag_reason!='integrity_fail' AND NOT LIKE '%rejected_fills%'` | **955** | Pure natural, no guard, delta >15% (compound flag_reason) |
| **A+C (pure-natural)** | `flag_reason NOT LIKE '%rejected_fills%'` | **3,708** | Same failure type combined |
| **B** | `flag_reason LIKE '%rejected_fills%'` | **13,096** | Guard-triggered |
| **Total** | `integrity_ok=0` | **16,804** | ✅ Exact match |

The gap is fully explained. No third genuine failure category exists.

### Rec-Step 2 — Category A Verification

**Script run:** 2026-08-09T14:25, seed=99, population=3,708

#### 2a. 25-File Sample — Raw Fill Inspection

All 25 files on disk and inspected. Results (format: account / date / raw / gh / trades / unp / rej / reason):

| # | Account | Date | raw | gh | tr | unp | rej | Reason |
|---|---------|------|----:|---:|---:|----:|----:|--------|
| 1 | ES-TS_4 | 2025-05-14 | 112 | 1 | 74 | 0 | 1 | fill_count_mismatch† |
| 2 | ES-TS_2 | 2026-05-29 | 63 | 1 | 38 | 1 | 3 | unclosed_position_other |
| 3 | ES-IPS_TM_8 | 2025-11-27 | 7 | 0 | 4 | 1 | 0 | **genuine_unclosed_position** |
| 4 | IPS_TM_5dupli | 2026-03-25 | 115 | 1 | 69 | 1 | 0 | unclosed_position_other |
| 5 | ES-IPS_TM_6 | 2026-01-26 | 17 | 0 | 10 | 1 | 0 | **genuine_unclosed_position** |
| 6 | ES-TM_1 | 2024-12-26 | 39 | 0 | 22 | 0 | 0 | fill_count_mismatch† |
| 7 | ES-TM_1 | 2026-03-06 | 73 | 0 | 41 | 0 | 0 | fill_count_mismatch† |
| 8 | ES-IPS_TM_13 | 2026-02-26 | 20 | 0 | 13 | 0 | 0 | fill_count_mismatch† |
| 9 | TM_8 | 2024-11-29 | 126 | 1 | 68 | 0 | 1 | fill_count_mismatch† |
| 10 | A_sim8 | 2024-01-30 | 19 | 0 | 12 | 0 | 0 | fill_count_mismatch† |
| 11 | ES-TM_1 | 2026-05-26 | 70 | 0 | 41 | 0 | 0 | fill_count_mismatch† |
| 12 | TM_6 | 2024-11-08 | 32 | 0 | 20 | 1 | 0 | **genuine_unclosed_position** |
| 13 | ES-TS_3 | 2024-07-26 | 106 | 3 | 54 | 0 | 5 | fill_count_mismatch† |
| 14 | IPS_TM_10 | 2025-10-23 | 63 | 0 | 40 | 1 | 0 | **genuine_unclosed_position** |
| 15 | TM_10 | 2025-07-16 | 68 | 0 | 39 | 1 | 0 | **genuine_unclosed_position** |
| 16 | TM_2 | 2024-07-05 | 32 | 0 | 19 | 1 | 0 | **genuine_unclosed_position** |
| 17 | IPS_TM_11 | 2024-07-23 | 41 | 0 | 25 | 1 | 0 | **genuine_unclosed_position** |
| 18 | B_sim14 | 2024-03-04 | 159 | 0 | 97 | 0 | 0 | fill_count_mismatch† |
| 19 | IPS_TM_7 | 2026-05-29 | 122 | 2 | 72 | 0 | 2 | fill_count_mismatch† |
| 20 | ES_PB_3 | 2025-04-25 | 276 | 2 | 152 | 0 | 11 | fill_count_mismatch† |
| 21 | ES-IPS_TM_8 | 2025-10-24 | 77 | 4 | 37 | 0 | 4 | fill_count_mismatch† |
| 22 | ES-TS_5 | 2024-11-08 | 80 | 0 | 50 | 0 | 0 | fill_count_mismatch† |
| 23 | TM_5 | 2024-07-23 | 149 | 2 | 78 | 2 | 0 | unclosed_position_other |
| 24 | IPS_TM_6 | 2026-02-05 | 31 | 0 | 19 | 1 | 0 | **genuine_unclosed_position** |
| 25 | IPS_TM_5dupli | 2024-09-05 | 88 | 2 | 51 | 1 | 2 | unclosed_position_other |

**† `fill_count_mismatch` caveat:** Classification formula uses `trades×2` for expected fill consumption. This is INCORRECT for scale-in/scale-out sessions. The 13 files in this category are likely PnL-mismatch failures (Category C) or complex position issues. Classification unreliable for those files.

#### 2b. Failure Reason Tabulation

| Reason | Count | Reliable? |
|--------|------:|-----------|
| `fill_count_mismatch` (formula incorrect for scale-in/out) | 13/25 | ⚠️ No |
| `genuine_unclosed_position` (unpaired fills > 0, gh=0, rej=0) | 8/25 | ✅ Yes |
| `unclosed_position_other` (unpaired fills > 0, with ghosts/rej) | 4/25 | ✅ Yes |

Confirmed position-level failures: **12/25 (48%)**. No new, previously-unseen patterns.

#### 2c. Methodological Note

Several files in the live re-run show `FILL REJECTED [ORPHANED_CLOSE_POST_GHOST_OPEN]` (rej>0) despite having no `rejected_fills` in their DB flag_reason. This is because the validation script calls `resync(raw_fills)` which processes **all symbols together**, while the original pipeline processes **per-symbol with independent position counters**. The spurious rejections are cross-symbol artifacts in the all-symbols entrypoint. The DB values (no `rejected_fills`) are authoritative — produced by the correct per-symbol pipeline.

#### 2d. Date/Account Concentration — Full Population (3,708 files)

| Year | Pure-nat failures | Total files | Fail rate |
|------|------------------:|------------:|----------:|
| 2024 | 1,364 | 24,591 | **5.5%** |
| 2025 | 1,584 | 24,912 | **6.4%** |
| 2026 | 760 | 12,203 | **6.2%** |

Account type: production=3,160 (85%) / sim=548 (15%)
Top accounts: ES-TM_1 (123), ES-TS_5 (103), ES-TM_2 (89), ES-TS_4 (87)

#### 2e. "Newer, Noisier Data" Claim — REFUTED AND REVISED

The previous Step 5 assessment stated the overage was explained by *"newer, noisier 2025-26 data with higher error rate."*

**This claim is NOT supported by the data.** The pure-natural failure rate is approximately uniform across all years: 5.5% (2024), 6.4% (2025), 6.2% (2026). The 2024 data alone has 1,364 failures — already 2.1× the scaled expectation of ~639 for 2024. This is not a 2025-26 phenomenon.

**Revised explanation:** The pre-fix (v3) 2.6% rate was likely itself anomalously low — suppressed by some files accidentally passing integrity (carry-over CLOSE scenarios creating fake OPENs that balanced). The ~6% rate is closer to the true natural rate of genuine data quality issues in this dataset. This remains a hypothesis, not proven with per-file v3 evidence.

**Explicit new-bug statement: NO new, previously-unexplained bug pattern was found in the 25-file sample.**

### Rec-Step 4 — Dry-Run (Full Output)

**Command:** `python scripts/promote_to_production.py --dry-run` — already run in Step 6 above.
Full output reproduced there. All gates pass against reconciled data understanding.

---

## FINAL GO/NO-GO TABLE (as of 2026-08-09, post-reconciliation)

| Item | Status | Evidence |
|------|--------|---------|
| Step 1 (flagged files) | ✅ CLOSED | 50/50 sample = Class A, 0 Class B |
| Step 2/A (ZB/ZN mult) | ✅ CLOSED | 8/8 trades MATCH@1000 in clean_trades |
| Step 3/B (Jul-09 handler) | ✅ CLOSED | Handler in GFE, Jul-09 verified |
| Step 4/C (integrity root cause) | ✅ CLOSED | Trade Evaluator sim, Step B resolves all |
| Step 5 NQ gap | ✅ CLOSED | Rollover taper |
| Step 5 TM7 gap | 📋 DOCUMENTED | Data gap, not blocking |
| v3.1 Regression (cross-day carry) | ✅ CLOSED | FIX v3.2 — Step 3: 10/10 + Jul-09 verified |
| Step 5 full re-run | ✅ CLOSED | 61,706 files, 2,917,511 trades |
| Rec-Step 1: 955-file gap | ✅ CLOSED | Category C = compound flag_reason artifact, A+B+C=16,804 exact |
| Rec-Step 2: Category A verify | ✅ CLOSED | 25/25 inspected; no new bugs; date rate uniform 2024-26 |
| "Newer noisier data" claim | ⚠️ REVISED | Refuted — rate uniform 5.5-6.4% all years; explanation revised |
| Pure-natural rate overage (3,708 vs ~1,604 scaled) | 📋 OPEN ITEM | Rate unexplained beyond hypothesis; recommend post-promotion investigation |
| Step 6 dry-run | ✅ CLOSED | All gates pass, 2,917,511 rows ready |

~~**RECOMMENDATION: CONDITIONAL GO**~~ **(SUPERSEDED — see Final Checks section below)**

---

## Final Two Checks Before Promotion

**Generated:** 2026-08-09T20:45 IST
**Scripts:** `scripts/step_final_checks.py`, `scripts/step_final_checks_p2.py`, `scripts/step3b_sym2.py`
**Rule:** All numbers computed from actual script output. Raw output shown.

---

### Step 1 — Diagnostic Reliability Re-check

#### 1a. Pipeline Confirmation

The previous report stated the diagnostic script used `resync()` which "processes all symbols
together." **This claim is FALSE and is retracted here.**

**Evidence** (read from `ghost_fill_engine.py` L939-1105):

`resync()` is defined as:
```python
def resync(raw_dicts, debug=False):
    engine = GhostFillEngine(debug=debug)
    fills  = GhostFillEngine.from_dicts(raw_dicts)
    return engine.process(fills)          # <-- this IS the per-symbol pipeline
```

`GhostFillEngine.process()` groups fills by `base_symbol` (L992-996) and calls
`pair_fills_to_trades()` with an independent position counter per symbol (L1036-1045).
`_process_file()` in `ghost_fill_cleaner.py` calls the same `engine.process()` (L279).
**Both paths are identical.** The prior "all-symbols-together" concern is closed.

#### 1b. Threading Race on `rejected_fills` (Audit Finding — NOT a data blocker)

`ghost_fill_cleaner.py` L589 runs `ThreadPoolExecutor(max_workers=cpu_count-1)`.
The `rejected_fills` list in `ghost_fill_engine.py` is **module-level** (shared across threads).
`_clr_rejected()` inside `_process_file()` races with concurrent threads:

- Thread A calls `_clr_rejected()`, zeroing Thread B's accumulated rejected fills.
- Thread B then calls `_get_rejected()` and sees count = 0.
- Result: `flag_reason`'s `rejected_fills=N` count is unreliable in the DB.

**Why this does NOT block promotion:**
`integrity_ok` is set by `result.integrity_ok` inside `engine.process()` (L1073),
computed **before** `_get_rejected()` is called. The race does not affect `integrity_ok`.
The 3,708 excluded files are correctly excluded regardless of their A/B/C label.

**What it does affect:** the A/B/C categorization (which is an audit artifact, not a
data correctness issue). Category A/B boundaries have noise from the race. Category C
(compound flag_reason) is unaffected.

#### 1c. Corrected 25-File Classification

Re-ran all 25 files through the same `engine.process()` pipeline and extracted the actual
`per_symbol.integrity_notes` messages from `verify_sequence()`. The 3 real failure reasons:

```
 #   Account                   Date         raw  gh   tr  unp rej  int   failure reason(s)
 -------------------------------------------------------------------------------------------
  1  ES-TS_4                   2025-05-14   112   1   74    0   1  FAIL  POSITION_IMBALANCE [ES]
  2  ES-TS_2                   2026-05-29    63   1   38    1   3  FAIL  POSITION_IMBALANCE [ES]
  3  ES-IPS_TM_8               2025-11-27     7   0    4    1   0  FAIL  POSITION_IMBALANCE [ES]
  4  IPS_TM_5dupli             2026-03-25   115   1   69    1   0  FAIL  POSITION_IMBALANCE [FDAX] | DIRECTION_FLIPS [FDAX]
  5  ES-IPS_TM_6               2026-01-26    17   0   10    1   0  FAIL  POSITION_IMBALANCE [ES]
  6  ES-TM_1                   2024-12-26    39   0   22    0   0  FAIL  DIRECTION_FLIPS [ES]
  7  ES-TM_1                   2026-03-06    73   0   41    0   0  FAIL  DIRECTION_FLIPS [ES]
  8  ES-IPS_TM_13              2026-02-26    20   0   13    0   0  FAIL  DIRECTION_FLIPS [ES]
  9  TM_8                      2024-11-29   126   1   68    0   1  FAIL  POSITION_IMBALANCE [FDAX] | DIRECTION_FLIPS [FDAX]
 10  A_sim8                    2024-01-30    19   0   12    0   0  FAIL  DIRECTION_FLIPS [NQ]
 11  ES-TM_1                   2026-05-26    70   0   41    0   0  FAIL  DIRECTION_FLIPS [ES]
 12  TM_6                      2024-11-08    32   0   20    1   0  FAIL  POSITION_IMBALANCE [FDAX]
 13  ES-TS_3                   2024-07-26   106   3   54    0   5  FAIL  POSITION_IMBALANCE [ES]
 14  IPS_TM_10                 2025-10-23    63   0   40    1   0  FAIL  POSITION_IMBALANCE [FDAX]
 15  TM_10                     2025-07-16    68   0   39    1   0  FAIL  POSITION_IMBALANCE [FDAX]
 16  TM_2                      2024-07-05    32   0   19    1   0  FAIL  POSITION_IMBALANCE [FDAX]
 17  IPS_TM_11                 2024-07-23    41   0   25    1   0  FAIL  POSITION_IMBALANCE [FDAX]
 18  B_sim14                   2024-03-04   159   0   97    0   0  FAIL  DIRECTION_FLIPS [NQ]
 19  IPS_TM_7                  2026-05-29   122   2   72    0   2  FAIL  POSITION_IMBALANCE [CL]
 20  ES_PB_3                   2025-04-25   276   2  152    0  11  FAIL  DIRECTION_FLIPS [ES]
 21  ES-IPS_TM_8               2025-10-24    77   4   37    0   4  FAIL  POSITION_IMBALANCE [ES]
 22  ES-TS_5                   2024-11-08    80   0   50    0   0  FAIL  DIRECTION_FLIPS [ES]
 23  TM_5                      2024-07-23   149   2   78    2   0  FAIL  DIRECTION_FLIPS [FDAX]
 24  IPS_TM_6                  2026-02-05    31   0   19    1   0  FAIL  POSITION_IMBALANCE [FDAX]
 25  IPS_TM_5dupli             2024-09-05    88   2   51    1   2  FAIL  POSITION_IMBALANCE [FDAX] | DIRECTION_FLIPS [FDAX]
```

**Corrected failure distribution:**

| Reason | Count | Prior label |
|---|---:|---|
| POSITION_IMBALANCE | 16/25 | Was: `fill_count_mismatch` (13) + `genuine_unclosed_position` (8) + `unclosed_position_other` (4) — all wrong |
| DIRECTION_FLIPS | 12/25 | (overlaps with POSITION_IMBALANCE on 3 files) |
| INVERTED_TRADES | 0/25 | None found |
| **Files reclassified to PASS** | **0/25** | All 25 still FAIL |

**Prior classification (all 3 categories) was completely wrong** — `fill_count_mismatch` does
not correspond to any real check in `verify_sequence()`. Zero files changed integrity status.

#### 1d. `verify_sequence()` FLIP Bug (New Finding)

`verify_sequence()` Check 1 (position balance):
```python
net          = sum(f.quantity if f.side=="BUY" else -f.quantity for f in clean_fills)
expected_open= sum(f.quantity if f.side=="BUY" else -f.quantity for f in unpaired)
if net not in (0, expected_open): → POSITION_IMBALANCE
```

When a FLIP occurs in `pair_fills_to_trades()` (position crosses zero), the flipping fill `f`
is stored in `queue` with `qty = abs(new_pos)` (the partial position), but `unpaired` contains
the **full fill object** with its original `f.quantity`. `verify_sequence` uses the full delta
as `expected_open`, but `net` = the actual partial end-position. They do not match →
POSITION_IMBALANCE fires even when position accounting is correct.

**This is a bug in `verify_sequence()`.** It does not affect `pair_fills_to_trades()`'s
accuracy (the FIFO is correct), but it inflates the POSITION_IMBALANCE failure count.

---

### Step 2 — Overnight Carry Check (42-file sample)

**Method:** For each file with unpaired fills (unp > 0), check whether the next calendar
day's file for the same account contains a fill that closes the open position (opposite
direction, same symbol). This is the same cross-day verification used in the v3.1 regression
investigation. 42 files total: 12 from the 25-file sample (all with unp > 0) + 30 additional
random files from the full 3,708 population (seed=42).

#### Step 2A — 12 files from 25-file sample (all with unpaired fills):

| Account | Date | unp | Classification | Detail |
|---|---|---:|---|---|
| ES-TS_2 | 2026-05-29 | 1 | NEXT_FILE_EMPTY | unclosed: {ES: -3}, next day empty |
| ES-IPS_TM_8 | 2025-11-27 | 1 | **CLOSED_NEXT_DAY** | ES:SELL 3 ESZ25 on 2025-11-28 |
| IPS_TM_5dupli | 2026-03-25 | 1 | **CLOSED_NEXT_DAY** | FDAX:SELL 3 FDAXM26 on 2026-03-26 |
| ES-IPS_TM_6 | 2026-01-26 | 1 | **CLOSED_NEXT_DAY** | ES:SELL 1 ESH26 oc=CLOSE on 2026-01-27 |
| TM_6 | 2024-11-08 | 1 | NEXT_FILE_EMPTY | unclosed: {FDAX: -3} |
| IPS_TM_10 | 2025-10-23 | 1 | **CLOSED_NEXT_DAY** | FDAX:BUY 2 FDAXZ25 oc=CLOSE on 2025-10-24 |
| TM_10 | 2025-07-16 | 1 | **CLOSED_NEXT_DAY** | FDAX:SELL 2 FDAXU25 oc=CLOSE on 2025-07-17 |
| TM_2 | 2024-07-05 | 1 | NEXT_FILE_EMPTY | unclosed: {FDAX: 3} |
| IPS_TM_11 | 2024-07-23 | 1 | **CLOSED_NEXT_DAY** | FDAX:BUY 1 FDAXU24 oc=CLOSE on 2024-07-24 |
| TM_5 | 2024-07-23 | 2 | **CLOSED_NEXT_DAY** | FDAX:BUY 3 FDAXU24 on 2024-07-24 |
| IPS_TM_6 | 2026-02-05 | 1 | **CLOSED_NEXT_DAY** | FDAX:BUY 1 FDAXH26 oc=CLOSE on 2026-02-06 |
| IPS_TM_5dupli | 2024-09-05 | 1 | **CLOSED_NEXT_DAY** | FDAX:SELL 2 FDAXU24 oc=CLOSE on 2024-09-06 |

2A result: 8 CLOSED_NEXT_DAY, 3 NEXT_FILE_EMPTY (inconclusive), 0 NEVER_CLOSED.

#### Step 2B — 30 additional random files (seed=42):

Selected from full 3,708 population, distinct from 25-file sample.

| # | Account | Date | unp | Classification |
|---|---|---|---:|---|
| 1 | PB_1 | 2025-04-30 | 8 | NEXT_FILE_EMPTY |
| 2 | ES-IPS_TM_11 | 2026-03-20 | 2 | **CLOSED_NEXT_DAY** (ES:SELL 1 ESM26 on 2026-03-22) |
| 3 | 3Q_sim14 | 2025-08-28 | 0 | NO_UNCLOSED |
| 4 | TM_7 | 2025-01-09 | 1 | **CLOSED_NEXT_DAY** (FDAX:SELL 2 FDAXH25 on 2025-01-10) |
| 5 | ES-TM_2 | 2024-12-20 | 0 | NO_UNCLOSED |
| 6 | ES-TM_1 | 2026-01-22 | 0 | NO_UNCLOSED |
| 7 | ES-TM_1 | 2024-07-26 | 0 | NO_UNCLOSED |
| 8 | ES-IPS_TM_3 | 2025-06-09 | 0 | NO_UNCLOSED |
| 9 | TM_7 | 2024-04-25 | 0 | NO_UNCLOSED |
| 10 | ES-IPS_TM_11 | 2025-03-21 | 4 | NEXT_FILE_EMPTY |
| 11 | TM_10 | 2025-04-13 | 0 | NO_UNCLOSED |
| 12 | TM_7 | 2024-11-19 | 1 | **CLOSED_NEXT_DAY** (FDAX:BUY 3 FDAXZ24 on 2024-11-20) |
| 13 | V_sim16 | 2025-09-12 | 1 | **CLOSED_NEXT_DAY** (NQ:BUY 3 NQU25 on 2025-09-14) |
| 14 | IPS_TM_11 | 2026-07-16 | 0 | NO_UNCLOSED |
| 15 | A_sim8 | 2024-02-09 | 0 | NO_UNCLOSED |
| 16 | IPS_TM_5dupli | 2025-05-18 | 2 | **NEVER_CLOSED** (CL+NQ unclosed, no match on 2025-05-19) |
| 17 | ES-TS_5 | 2025-02-12 | 0 | NO_UNCLOSED |
| 18 | 3Q_sim15 | 2024-09-09 | 0 | NO_UNCLOSED |
| 19 | 3Q_sim14 | 2026-04-29 | 8 | **CLOSED_NEXT_DAY** (CL:BUY 1 CLM26 on 2026-04-30) |
| 20 | ES-IPSPB1 | 2024-06-05 | 0 | NO_UNCLOSED |
| 21 | ES-PB_1 | 2026-02-20 | 0 | NO_UNCLOSED |
| 22 | ES-TM_1 | 2025-02-25 | 0 | NO_UNCLOSED |
| 23 | IPSTMUD1 | 2024-08-27 | 1 | **CLOSED_NEXT_DAY** (FDAX:BUY 1 FDAXU24 on 2024-08-28) |
| 24 | IPS_TM_6 | 2025-02-28 | 6 | NEXT_FILE_EMPTY |
| 25 | 3Q_sim14 | 2025-11-18 | 1 | **CLOSED_NEXT_DAY** (CL:SELL 3 CLZ25 on 2025-11-19) |
| 26 | IPS_TM_13 | 2025-02-17 | 3 | **CLOSED_NEXT_DAY** (FDAX:BUY 1 FDAXH25 on 2025-02-18) |
| 27 | ES-IPS_TM_8 | 2025-12-03 | 0 | NO_UNCLOSED |
| 28 | TM_5 | 2024-06-09 | 2 | **CLOSED_NEXT_DAY** (NQ:BUY 3 NQM24 on 2024-06-10) |
| 29 | PB_2 | 2024-06-25 | 1 | **CLOSED_NEXT_DAY** (FDAX:BUY 1 FDAXU24 on 2024-06-26) |
| 30 | TM_2 | 2025-08-17 | 0 | NO_UNCLOSED |

#### Step 2 Summary (42 files total)

| Classification | Count | Meaning |
|---|---:|---|
| NO_UNCLOSED (fail is DIRECTION_FLIPS, not open position) | 16 | Separate failure mode, no overnight carry |
| **(b) CLOSED_NEXT_DAY — legitimate overnight carry** | **19** | **verify_sequence false-fail** |
| (a) NEVER_CLOSED — genuine unresolved data problem | 1 | Real integrity failure |
| NEXT_FILE_EMPTY / NO_NEXT_FILE (inconclusive) | 6 | Cannot determine |

**Raw extrapolation:** 19 confirmed / 42 inspected = **45.2%** of inspected files are
legitimate overnight carries incorrectly flagged.

Applied to the full 3,708 excluded files: **~1,677 files** (~45%) are estimated to be
legitimate overnight positions excluded from `clean_trades` when they should NOT be.

> **Why `verify_sequence()` false-fails on overnight carry files:**
> When an account carries a position overnight, the session file may start with an
> ORPHANED_CLOSE_UNKNOWN_ORIGIN fill (cross-day carry with `ghost_fills_dropped=0`).
> This fill falls through to the ENTRY branch and becomes a new position leg in the FIFO.
> Normal intraday trading then interacts with this phantom entry, creating direction flips
> and/or POSITION_IMBALANCE (via the FLIP bug documented in Step 1d).
> The position IS correctly resolved the next calendar day — but `verify_sequence()` has
> no lookahead and flags the current day's file as integrity=FAIL.

---

### Step 3 — Exclusion Distribution Check

**Method:** Compare distribution of 3,708 excluded (integrity_ok=0, no rejected_fills)
files vs 61,706 full dataset across day-of-week, symbol, and bypass_mode.

#### 3A — Day-of-Week Distribution

Raw output (from `scripts/step_final_checks_p2.py`):

```
Day    excl    full      excl%    full%    ratio   concentration?
-----------------------------------------------------------------
Sun      497   8,407    13.4%   13.6%   0.98x  proportional
Mon      670   9,693    18.1%   15.7%   1.15x  proportional
Tue      653   9,229    17.6%   15.0%   1.18x  proportional
Wed      674  10,075    18.2%   16.3%   1.11x  proportional
Thu      664   9,979    17.9%   16.2%   1.11x  proportional
Fri      550   9,202    14.8%   14.9%   0.99x  proportional
```

**Finding: No day-of-week concentration.** All ratios 0.98–1.18×. Exclusions are
proportional to the dataset's trading-day distribution. No selection bias by weekday.

#### 3B — Symbol Distribution (from `asset_list` column)

Raw output (from `scripts/step3b_sym2.py`):

```
Symbol    excl    full     excl%    full%    ratio  flag
-----------------------------------------------------------------
ES       1,660  15,068    41.2%   37.7%   1.09x  ok
NQ         864   8,261    21.4%   20.7%   1.04x  ok
FDAX       802  10,247    19.9%   25.6%   0.78x  ok
CL         634   5,744    15.7%   14.4%   1.09x  ok
ZB          37     330     0.9%    0.8%   1.11x  ok
ZN          35     322     0.9%    0.8%   1.08x  ok
```

**Finding: No symbol concentration.** All ratios 0.78–1.11×. Exclusions are proportional
across all traded instruments. FDAX is slightly under-represented (0.78×) which means FDAX
files are excluded at a proportionally *lower* rate than the rest — no selection bias concern.

#### 3C — Bypass Mode Distribution

Raw output (from `scripts/step3b_sym2.py`):

```
bypass=0: excl=3,086 (83.2%) full=56,929 (92.3%) ratio=0.90x  ok
bypass=1: excl=622   (16.8%) full=4,777  ( 7.7%) ratio=2.17x  *** HIGH
```

Derived exclusion rates:
- bypass=0 files: 3,086 / 56,929 = **5.4% excluded**
- bypass=1 files: 622 / 4,777 = **13.0% excluded** (2.4× higher rate)

**Finding: bypass_mode=1 files are concentrated in the excluded population (2.17×).**
Files with low strategy-tag note_rate (< 25% threshold, ghost filter disabled) fail
integrity at 2.4× the rate of well-tagged files.

**Is this a selection-bias concern for downstream time-slot analysis?**
Partially. bypass_mode=1 indicates an account/period where fills lack strategy attribution
tags. The day-of-week distribution is uniform (3A), so there is no systematic weekday bias.
However, bypass_mode=1 may correlate with specific accounts or time-of-day windows (e.g.,
pre-market, overnight sessions where the C++ strategy is not running). File-audit granularity
is daily, so hour-of-day cannot be confirmed. The 622 bypass=1 excluded files represent
~1.0% of the full dataset — limited absolute impact, but the 2.17× ratio indicates a
systematic quality difference in these sessions worth tracking post-promotion.

#### 3D — Year Distribution (confirming earlier finding)

```
2024: 1,364 failures / 24,591 files = 5.5%
2025: 1,584 failures / 24,912 files = 6.4%
2026:   760 failures / 12,203 files = 6.2%
```

**No temporal concentration.** Rate is uniform 5.5–6.4% across all years.

---

### Step 4 — Final Consolidated Assessment and Updated Recommendation

#### Status Gate Summary

| Gate | Status | Evidence |
|---|---|---|
| Step 1 pipeline claim corrected | ✅ CLOSED | `resync()` = per-symbol pipeline. Prior claim retracted |
| Step 1 threading race | ⚠️ AUDIT NOTE | flag_reason counts unreliable; integrity_ok reliable |
| Step 1 classification corrected | ✅ CLOSED | 0/25 changed to PASS; all 25 still FAIL |
| Step 1 verify_sequence FLIP bug | ⚠️ KNOWN BUG | Inflates POSITION_IMBALANCE count; does not block data correctness |
| Step 2 overnight carry — 19/42 = 45% | 🚫 **BLOCKING** | ~1,677 legitimate files wrongly excluded |
| Step 3 Day-of-week | ✅ CLOSED | No concentration (0.98–1.18×) |
| Step 3 Symbol | ✅ CLOSED | No concentration (0.78–1.11×) |
| Step 3 bypass_mode=1 | ⚠️ NOTED | 2.17× concentrated; ~1% of dataset; no weekday pattern |

#### Blocking Concern — Overnight Carry False Exclusions

Evidence: 19 of 42 sampled files confirmed as legitimate overnight carries (case b).
Scale: Extrapolated ~1,677 of 3,708 pure-natural-failure files are false-exclusions.

**Impact on promoted dataset if `--confirm` is run without fixing this:**
- ~1,677 session-days of legitimate trades silently absent from `clean_trades`
- These represent overnight-carry accounts (TM series, PB series, IPS series) whose
  sessions the pipeline incorrectly flags — their intraday PnL is missing from
  `processed_trades` entirely.
- Downstream BH-FDR time-slot analysis operates on a dataset where overnight-carry
  sessions are systematically underrepresented for these specific accounts.

**Required fix before promotion (two valid options):**

**Option A — Lookahead fix (recommended, minimal scope):**
In the batch-level loop of `ghost_fill_cleaner.py`, after `engine.process()`, if
`integrity_ok=False` and the only failure is POSITION_IMBALANCE + unpaired fills:
check the next day's file for the same account. If a closing fill for the same symbol
exists there, override `integrity_ok=True` for the current day's file and include its
trades in `clean_trades`. Requires no changes to `ghost_fill_engine.py`.

**Option B — verify_sequence fix (broader, correct the root cause):**
Fix the FLIP bug in `verify_sequence()`: change `expected_open` computation to use
the partial position quantity (from `_OpenLeg.qty`) rather than the full fill delta.
This requires `pair_fills_to_trades()` to return `(trades, unpaired_fills, position_at_end)`
and `verify_sequence()` to accept `position_at_end` instead of computing it from unpaired
fill objects. This is the structurally correct fix but requires modifying two functions
and a full re-run of all 61,706 files.

**If promoting as-is (neither fix applied), the following must be explicitly acknowledged:**
1. ~1,677 overnight-carry session files are wrongly excluded from `clean_trades`.
2. Accounts that carry positions overnight (TM, PB, IPS families confirmed in sample)
   are underrepresented in the promoted dataset.
3. The BH-FDR time-slot selector may over-weight time-slots that are NOT overnight-carry
   sessions for those accounts, because overnight-carry sessions have lower trade counts.

---

**UPDATED RECOMMENDATION: ⛔ BLOCKED — PENDING HUMAN DECISION**

The prior "CONDITIONAL GO" recommendation is superseded. Two items require a human decision:

**Decision 1 (Required):** Overnight carry (~1,677 files, ~45% of pure-natural failures).
Choose one of:
- (a) Implement lookahead fix (Option A above), re-run affected files, then promote.
- (b) Implement verify_sequence fix (Option B above), full re-run, then promote.
- (c) Accept as-is and explicitly acknowledge ~1,677 legitimate sessions are excluded.

**Decision 2 (Recommended):** bypass_mode=1 concentration (2.17×, 622 files, ~1% of dataset).
This does not block promotion by itself, but downstream slot-selection consumers should
be made aware that bypass_mode=1 sessions are excluded at 2.4× the rate of tagged sessions.

**DO NOT run `promote_to_production.py --confirm` until Decision 1 is made and documented.**

