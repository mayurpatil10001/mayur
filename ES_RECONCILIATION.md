# ES (E-mini S&P 500 Futures) Fill Reconciliation Report

**Instrument Target:** ES / MES (CME Globex E-mini S&P 500 Futures)  
**Date Range Audited:** 2023-09-04 to 2025-10-31  
**Multiplier:** $50.00 per index point | **Commission:** $4.20 round-turn  

---

## Step 1 — Session Boundary Verification
- **Exchange:** CME Globex
- **Trading Hours:** Sunday 18:00 ET to Friday 17:00 ET with daily maintenance break from **17:00 ET to 18:00 ET**.
- **17:00 NY Session Boundary Rule Evaluation:** **CORRECT**.
  - CME Globex completely halts trading for ES between 17:00 ET and 18:00 ET every business day.
  - Any trade entered prior to 17:00 ET and exiting after 17:00 ET crosses the exchange maintenance window and represents an overnight/multi-session holding.

---

## Step 2 & 3 — Raw Fill Ledger & Bucket Classification

All execution records for ES across the target date range were parsed and categorized into exact non-overlapping buckets:

| Category / Bucket | Trade Count | Equivalent Fills (2/trade) | PnL Sum | Win Rate | Gross Profit | Gross Loss |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Pre-Resync Total (Old)** | 301,317 | 602,634 | $-11,289,025.00 | 42.78% | — | — |
| **(a) Matched Survived Trades** | 3,712 | 7,424 | $-43,250.00 | 38.23% | — | — |
| **(b+d+e) Removed Trades** | 297,605 | 595,210 | $-11,245,775.00 | 42.84% | $29,276,937.50 | $-40,522,712.50 |
| **Post-Resync Total (New)** | 37,322 | 74,644 | $-3,440,918.75 | 45.71% | — | — |

---

## Step 4 — Invariant Verification
- **Flat Position Status (+N / -N):** **PASSED**.
  - At the end of every trading session, all closed ES trades net to exactly 0 long and 0 short positions per account.
  - Unmatched legs remaining at session boundaries are explicitly isolated into Bucket (e) without corrupting subsequent session states.

---

## Step 5 — Bucket (b) Ghost Fill PnL Audit for ES

- **Removed ES Trade Count:** 297,605
- **Removed ES Net PnL Sum:** **$-11,245,775.00**
- **Removed ES Win Count:** 127,482 (42.84%) | **Gross Profit:** $29,276,937.50
- **Removed ES Loss Count:** 167,073 (56.14%) | **Gross Loss:** $-40,522,712.50
- **Gross Loss Dollar Share:** **58.06%**

### Selection Bias Assessment for ES:
- Gross loss dollar share is **58.06%** of removed dollar volume for ES.
- **Verdict:** ⚠️ Ghost removal for ES disproportionately removes losing trade volume.

---

## Step 6 — Summary vs Claimed Aggregate Figures

- **Pre-Fix ES Performance:** 301,317 trades, PnL: **$-11,289,025.00**.
- **Post-Fix ES Performance:** 37,322 trades, PnL: **$-3,440,918.75**.
- **Net PnL Change from Fix on ES:** **+$7,848,106.25**.
