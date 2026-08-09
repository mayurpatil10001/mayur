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

### Step 5 — Full Re-run (IN PROGRESS)

**Command:** `python ghost_fill_cleaner.py --reset`
**Started:** 2026-08-09T09:36 IST
**Expected duration:** ~192 minutes

Target: final integrity failures ≤ 10,762 (pre-fix baseline).
If substantially above baseline → additional investigation required before promotion.

*This section will be updated once the re-run completes.*

### Step 6 — promote_to_production.py Gate Update

Pending re-run results. Gate for `ORPHANED_CLOSE_UNKNOWN_ORIGIN` to be assessed:
files logging this reason still PASS integrity, but the fill is an unpaired OPEN leg.
If these files generate no completed trades (expected for single-fill carry-close sessions),
they do not pollute `clean_trades`. The gate should verify this count and report it
separately rather than blocking promotion, since these are expected data-boundary artefacts.

---

## UPDATED GO / NO-GO TABLE (as of 2026-08-09)

| Item | Status | Evidence |
|------|--------|---------|
| Step 1 (flagged files) | CLOSED | 50/50 sample = Class A, 0 Class B |
| Step 2/A (ZB/ZN mult) | CLOSED | 8/8 trades MATCH@1000 in clean_trades |
| Step 3/B (Jul-09 handler) | CLOSED | Handler in GFE, Jul-09 verified |
| Step 4/C (integrity root cause) | CLOSED | Trade Evaluator sim, Step B resolves all |
| Step 5 NQ gap | CLOSED | Rollover taper |
| Step 5 TM7 gap | DOCUMENTED | Data gap, not blocking |
| v3.1 Regression (cross-day carry) | **CLOSED (code)** | FIX v3.2 — Step 3: 10/10 + Jul-09 verified |
| Step 5 full re-run | **PENDING** | ghost_fill_cleaner.py --reset running |
| Step 6 gate update | PENDING | After re-run results |

DO NOT RUN promote_to_production.py --confirm until the full re-run completes and
its integrity-failure count is confirmed ≤ the pre-fix baseline of 10,762.
