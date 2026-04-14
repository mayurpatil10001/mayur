# Live Trading Playbook

> **Purpose:** Step-by-step decision framework for transitioning from simulated data to live trading. Read this before you fund an account.

---

## Context: What Your Data Is

All current data comes from Sierra Chart simulated feeds (`D:\SierraChart_Simulated_Feed\`). This is **paper trading** — real market prices, real execution logic, but no real money. The statistical patterns are real, but slippage and execution quality may differ in live. Everything in this playbook accounts for that gap.

---

## The 5-Step Go/No-Go Framework

```
Step 1: Method Bake-Off         → Which selection method wins OOS?
Step 2: Best Bins Filter        → Which specific bins fit a $1000 account?
Step 3: Correlation Check       → Are my candidate bins actually diversified?
Step 4: Regime Risk Check       → Does the edge survive in all VIX regimes?
Step 5: Go-Live + Live Tracker  → Trade, then validate daily
```

### Step 1 — Method Bake-Off (Platform: "Method Bake-Off" tab)

**Goal:** Find which of the 4 methods produces the most reliable out-of-sample (OOS) results for your symbol.

**What to look for (in order of importance):**

| Metric | Minimum bar | Notes |
|--------|------------|-------|
| Permutation p-value | < 0.05 | Results are not random |
| Consistency % | > 55% | More than half of test folds profitable |
| OOS Sharpe | > 0.5 | Minimum risk-adjusted return |
| OOS Win Rate | > 60% | |
| Profit Factor | > 1.3 | |

**Method definitions:**
- **Persistence** — selects edges that are profitable in most months (profitable_months / total_months). Most conservative. Best for live because it answers "does this show up consistently?"
- **Classic** — selects by highest avg profit per trade. Simple. Can overfit to big-win periods.
- **Statistical EV** — selects by `avg_trade × win_rate`. Weighted toward reliable frequency.
- **Ensemble** — multi-window (30/45/90 day) vote with VIX regime bonus. Most adaptive but most complex.

**Rule:** Use the method with the highest Consistency % AND p-value < 0.05. When in doubt, Persistence is the safest for a first live deployment.

---

### Step 2 — Best Bins Filter (Platform: Recommendations → Matrix tab → "Best Bins" button)

**Goal:** Narrow the 200+ matrix cells down to bins safe for a $1000 account.

**Enter your account size in the input field and click "Best Bins for $1000".**

The filter applies these criteria (all must pass):

| Criterion | Threshold | Why |
|-----------|-----------|-----|
| Min Trades | ≥ 150 | Statistical confidence |
| Min Win Rate | ≥ 68% | Small account cannot survive frequent losing streaks |
| Min Avg Profit | ≥ $20 | After slippage (assume ~$12/trade), real edge ≥ $8 |
| Min Profit Factor | ≥ 1.5 | Gross wins ÷ gross losses must be profitable enough to sustain |
| Risk Score | ≤ 25% | Single loss never > 25% of account |
| Recovery Trades | ≤ 3 | Max 3 wins needed to recover 1 loss |

**Composite score** = 30% Profit Factor + 30% Win Rate + 20% Avg Trade + 20% Risk Safety

Gold-bordered cells are qualified. The rank badge (1, 2, 3...) shows priority order. Dimmed cells do not qualify.

**Cell tooltip** (hover any cell) now shows:
- Avg Winner / Avg Loser
- Profit Factor
- Largest Win / Largest Loss
- Health status (STABLE / DRIFTING / CRITICAL)

---

### Step 3 — Correlation Check (Platform: "Correlation" tab)

**Goal:** Confirm your top bins are NOT highly correlated with each other.

**Process:**
1. Run Step 2 first — the top 5 bins auto-populate in the Correlation tab
2. Or paste account names manually (comma-separated)
3. Click "Compute Correlation"

**Rules:**
- Correlation > 0.7 → **Do not trade both simultaneously.** They will move together. You are doubling your risk, not diversifying.
- Correlation 0.3-0.7 → Acceptable but monitor. If both go down on the same day, investigate.
- Correlation < 0.3 → Good diversification.

**The ideal portfolio for $1000:** 3-4 bins with low cross-correlation, each from a different time slot or day-of-week.

---

### Step 4 — Regime Risk Check (Platform: Recommendations → Matrix tab → "Show Regime Risk" toggle)

**Goal:** Verify the edge works in all VIX environments, not just low-vol conditions.

**Toggle "Show Regime Risk" on the matrix.** Each cell gets an icon:
- **🛡 Green Shield** — Profitable in Low, Medium, AND High VIX regimes. These are your strongest edges.
- **⚠ Yellow Warning** — Profitable in 2/3 regimes. Acceptable, but know which regime kills it.
- **🚨 Red Danger** — Only profitable in 1 regime. High risk for live trading.

**Fragility Score** (in tooltip): `(low_vol_avg - high_vol_avg) / low_vol_avg`
- Fragility > 0.5 = the edge loses half its value in high volatility
- Fragility > 0.8 = avoid unless you can time regime entry

**Rule:** Only trade cells with 🛡 or ⚠ (2/3 regimes). Never go live with a 🚨 cell in a $1000 account.

---

### Step 5 — Go-Live and Live Tracker (Platform: "Method Bake-Off" tab → "Live Trading Tracker")

**Before you start:**
- [ ] Steps 1-4 completed
- [ ] Final bin list has < 6 bins, each with low cross-correlation
- [ ] All selected bins have 🛡 or ⚠ regime status
- [ ] Sierra Chart autotrader is configured for selected permutations only
- [ ] Daily loss limit set in SC: $150/day (15% of $1000)
- [ ] Weekly loss limit: $300

**After each trading day:**
1. Import Trade Activity Log into the platform (Monitoring tab → Import)
2. Platform will process and classify trades

**Weekly check (every Sunday):**
1. Open "Method Bake-Off" tab → "Live Trading Tracker"
2. Enter your go-live date and the method you used
3. Click "Check Live vs Expected"
4. Review the verdict:
   - **ON TRACK** — Continue trading. Review next week.
   - **DRIFTING** — Results are below expected but within 2σ. Continue but reduce position size mentally.
   - **STOP AND RE-EVALUATE** — One or more bins are > 2σ below expected. Pause and re-run Step 1.

---

## $1000 Account Rules (Non-Negotiable)

| Rule | Value | Reason |
|------|-------|--------|
| Max concurrent positions | 1 | Margin + risk management |
| Daily loss limit | $150 (15%) | If hit, stop trading for the day |
| Weekly loss limit | $300 (30%) | If hit, go back to simulation for 1 week |
| Max bins trading simultaneously | 3 | Correlation risk |
| Min wait before adding new bin | 30 trading days | Need data to confirm the edge is working |
| Re-evaluate trigger | 5 consecutive loss days in any bin | Could be regime change or edge decay |

---

## Recommendations Matrix Behavior (Current)

- **Modes available in Recommendations Matrix:** Persistence / Classic / Statistical / Ensemble.
- **In-matrix filters:** Min Persistence %, Min Trades, Min Avg $ are applied directly to matrix recomputation.
- **Best Bins overlay:** highlights qualifying bins only; it does not change the winner-per-cell ranking logic.
- **Regime Risk overlay:** shows regime robustness icons (all regimes / 2 of 3 / 1 of 3).
- **Selection-aware right panel:** selecting custom matrix bins marks right-side panels as stale/paused until clear/refresh.
- **Live Health Status row:** removed from Recommendations matrix header.

### Day/Session Mapping (Critical)

This project uses session-aware indices from `processed_trades.day_of_week`:

- `6` = **Sunday evening session** (market re-open)
- `0..4` = Monday..Friday
- `5` = Saturday (excluded)

Recommendations and Discovery now use the same session basis (Sunday+Mon..Fri shown, Saturday excluded).

---

## How to Read the Metrics

### In the Matrix Cell (standard/persistence/classic view)
```
TM_D-R-1_1       ← account/permutation name
$38.3  447  84%  71%  ← Avg PnL, Trades, W/L %, Persistence
● STABLE              ← health status vs last 30 days
```

### In the Cell Tooltip (hover)
| Field | What it means |
|-------|--------------|
| Avg PnL | Average profit per trade including winners and losers |
| Trades | Historical trade count for this bin |
| W/L % | Percentage of profitable trades |
| Persistence | Percent of profitable months for this bin |
| Win Rate | % of trades that end positive |
| Profit Factor | Gross profit ÷ gross losses. > 1.5 is good. > 2.0 is excellent |
| Avg Winner | Average size of winning trades |
| Avg Loser | Average size of losing trades |
| Recovery Trades | How many wins needed to recover 1 loss (Avg Loser ÷ Avg Winner) |
| Largest Win / Loss | Extremes — watch the largest loss, it's your worst-case single event |
| Health STABLE | Recent 30-day avg is ≥ 90% of historical avg |
| Health DRIFTING | Recent avg is positive but below historical |
| Health CRITICAL | Recent avg has gone negative |

### In the Method Bake-Off
| Field | What it means |
|-------|--------------|
| Consistency % | % of walk-forward test folds that were profitable OOS |
| Permutation p-value | Probability the OOS results are random. < 0.05 = statistically significant |
| OOS Sharpe | Risk-adjusted return annualized. 0.5+ = tradeable. 1.0+ = good. 1.5+ = excellent |
| Avg Edges/Fold | How many bins the method selects per fold. More = more diversified but more risk |

### In the Live Tracker
| Z-Score | Meaning | Action |
|---------|---------|--------|
| > −1.5 | ON TRACK | Continue |
| −1.5 to −2.5 | DRIFTING | Watch closely, reduce to 50% if trend continues |
| < −2.5 | CRITICAL | Pause this bin immediately |

---

## When to Scale Up

After 30 live trading days, check:
1. Annualized Sharpe > 0.5 from live trades
2. Directional accuracy > 55% (actual avg trade direction matches expected)
3. At least 20 live trades per selected bin

If all 3 pass:
- Add 1 more bin from your qualified list (the next-highest composite score)
- Do NOT increase position size yet
- Wait another 30 days

After 60 days with all bins on track:
- Consider doubling account size via wire transfer (not margin)
- Re-run the full 5-step framework with new account size constraints

---

## When Results Don't Match Expectations

### Scenario A: Actual avg trade is 30-50% below expected
This is normal for the first 30 days. Slippage, timing differences, and small sample size all contribute. Continue if Sharpe > 0.

### Scenario B: Actual avg trade is > 50% below expected for 2+ weeks
1. Check if VIX regime has changed (VIX tab) — are you in a regime where the edge is weak?
2. Check if the permutation still appears in the current matrix — has the historical edge decayed?
3. If both are fine, check SC execution logs for fill quality issues

### Scenario C: Win rate drops > 10 percentage points below expected
Strong signal that something changed. Do not wait for more data — pause and re-run Steps 1-4.

### Scenario D: Multiple bins all drift simultaneously
This is almost always a regime change. Check VIX. If you moved from Low to High vol, some edges will underperform. Wait for regime to normalize before re-evaluating.

---

## Questions From Setup (Answers)

**Q1: How do I compare which method is better?**
Use the "Method Bake-Off" tab. Run walk-forward for all 4 methods with identical parameters. The method with highest Consistency % AND p-value < 0.05 wins. Persistence is the safest starting point.

**Q2: How do I set up Sierra Chart workbooks automatically?**
Deferred to a separate plan. Currently, this platform exports the winning permutation per bin. Use that list to configure SC charts manually. SC workbook automation (via .Cht XML generation) is planned next.

**Q3: How do I know real results match predictions?**
Use the Live Tracker in the "Method Bake-Off" tab. Set your go-live date, click "Check Live vs Expected." The z-score per bin tells you if actual performance is within normal statistical variance of expected. Z > -1.5 = on track.

**Q4: Best bins for $1000?**
Click the "Best Bins for $1000" button on the Matrix tab. Cells that qualify get a gold border with a rank badge. Non-qualifying cells are dimmed. The Top 5 summary card below the matrix shows expected PnL/day and worst-case daily loss.

**Q5: What would an experienced quant trader recommend?**
See the "Next Steps" section below.

---

## Next Steps (Quant's Recommendation)

In priority order:

1. **Run the Method Bake-Off for NQ/ES** — determine which method to use (15 minutes)
2. **Run Best Bins with $1000 filter** — get your shortlist of 5-8 candidates (5 minutes)
3. **Run Correlation Check on candidates** — eliminate correlated pairs (5 minutes)
4. **Check Regime Risk on final list** — eliminate 🚨 cells (2 minutes)
5. **Set up SC for only those bins** — autotrader configs for your final 3-4 bins
6. **Trade for 2 weeks in sim** with the same filters applied — baseline live-sim performance
7. **If sim matches paper expectations (within 30%)** → go live with $1000
8. **Import daily, check Live Tracker weekly** — first 30 days are validation, not profit-generation
9. **After 30 days: scale decision** — if on track, add 1 bin or add capital

---

## Glossary

| Term | Definition |
|------|-----------|
| Permutation | One specific account/study configuration (e.g., `TM_D-R-1_1`) |
| Bin | A 30-minute time slot + day of week combination (e.g., 14:00 Wednesday) |
| OOS | Out-of-Sample — results on data the model was NOT trained on |
| Persistence | % of months an edge was profitable |
| CWEV | Confidence-Weighted Expected Value — probability × mean return |
| p-value | Probability the result is random. < 0.05 means statistically significant |
| Fragility | How much the edge weakens in high-volatility regimes |
| Z-Score | Standard deviations from expected. < -2 = statistically unusual |
| Walk-Forward | Testing methodology: train on past, test on future, repeat rolling |

---

*Last updated: March 2026. This document is updated when significant platform features change.*
