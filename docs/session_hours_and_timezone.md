# Session Hours and Timezone (17:00–18:00 NY)

This document explains why trade recommendations can appear in the 17:00–18:00 slot and how the platform enforces US Eastern (New York) session hours.

## Session rules (US Eastern)

- **Session boundary:** 17:00 NY is end-of-day; FIFO and session date roll at 17:00 (see `IMPORT_SHIELD_CORE_RULES.md`).
- **Closed window:** No trading **between 17:00 and 18:00** NY (market closed).
- **Evening session:** Market opens again at **18:00** NY; trades at 18:00 and later are valid.

So we must **exclude only 17:00 ≤ time < 18:00** (NY) and **allow** time &lt; 17:00 and time ≥ 18:00.

## Why 17:00–18:00 appeared in the first place

Possible causes:

1. **Timezone mismatch**  
   `entry_time` in the database is stored as **UTC** (see `trade_import_logic_and_validation.md`). If analytics used `strftime('%H:%M', entry_time)` without converting to NY, then:
   - “17:00” in the grid could be **17:00 UTC** ≈ 12:00/13:00 ET (market open), or  
   - We could be filtering/session logic in UTC instead of NY.

2. **Session filter too broad**  
   A filter of the form `entry_time < '17:00'` excludes everything from 17:00 onward, including **18:00, 19:00, …** (evening session). So the rule was wrong: we must exclude only the **closed** window 17:00–18:00, not “after 17:00”.

3. **Time slot built from raw `entry_time`**  
   If `time_slot` was derived from `entry_time` (UTC) instead of NY, then the grid showed UTC hours. So “17:00” might have been 12:00 or 13:00 ET (valid trading), and the session filter was applied in the wrong timezone.

## Fixes applied

1. **Session window (all analytics)**  
   - Filter: exclude only **17:00 ≤ NY time < 18:00**.  
   - In SQL (when using NY fields): `(hour_of_day < 17 OR hour_of_day >= 18)`.  
   - In SQL (when using string time): `(strftime('%H:%M', …) < '17:00' OR strftime('%H:%M', …) >= '18:00')`.  
   - So 18:00 US Eastern is **allowed**.

2. **Use NY time for session and slots**  
   - `processed_trades` has **`hour_of_day`** and **`day_of_week`** computed in **America/New_York** at import (binary parser).  
   - **`minute_of_hour_ny`** was added so discovery can build **time_slot** in NY (e.g. `08:00`, `08:30`).  
   - Discovery (and any session filtering) uses these NY fields so that:
     - Session filter is correct (no trades 17:00–18:00 NY, allow 18:00+).
     - Grid and recommendations are in US Eastern.

3. **Frontend**  
   - Same rule: exclude only 17:00–18:00; allow `time_slot >= '18:00'` and `time_slot < '17:00'`.

## Day of Week Convention

The platform uses Python's `weekday()` convention for storing and processing data:
- **0: Monday**
- **1: Tuesday**
- **2: Wednesday**
- **3: Thursday**
- **4: Friday**
- **5: Saturday** (Typically excluded from analytics)
- **6: Sunday** (Evening session starting 18:00 NY)

This convention is applied in:
- `processed_trades` table (`day_of_week` column)
- Recommendation Matrix (Persistence, Classic, Statistical modes)
- Discovery Explorer

## Data Freshness Rule

To ensure recommendations are based on current market behavior:
- **30-Day Limit:** All recommendation and discovery engines (Persistence, Classic, Statistical, and Ensemble) are gated to only consider accounts that have been active in the last 30 days.
- **Outdated Data:** Accounts that have not traded within the last 30 days are automatically excluded from the matrix views to prevent following "stale" edges.

## Visual Feedback

When filters are changed or analytics are recalculated, a **Recalculation Progress Bar** (animated banner) is displayed in the Recommendations tab to provide continuous feedback of the background processing.
