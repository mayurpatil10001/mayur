# Analytics Freshness & Performance Optimization (April 2026)

## Overview
This update addresses critical requirements for **Data Freshness** and **Dashboard Performance**. It ensures that stale accounts are strictly excluded from all recommendation logic while significantly reducing latency during matrix mode switching.

## 1. 30-Day Freshness Gate (The "Banned" List)
A strict 30-day freshness gate is now enforced across all recommendation modes (Persistence, Classic, Statistical, and Ensemble 2.0).

### Enforcement Mechanisms
*   **SQL-Layer CTE Filter**: All recommendation queries now utilize an optimized Common Table Expression (CTE) called `recent_accounts`. This CTE identifies accounts with at least one trade on the specific symbol within the last 30 days using native SQLite date functions: `HAVING MAX(entry_time) >= date('now', '-30 days')`.
*   **Python-Layer Fail-Safe**: A secondary check is performed in the FastAPI backend. If an account like `TM_5` or `TM_8` (which are explicitly banned) somehow appears in the result set, or if they are tagged with a "NEW/NO_DATA" status, the backend **pops them out** of the final JSON before it is served to the frontend.
*   **Global Exclusion**: This filter applies to the Matrix, Discovery Hub, and Portfolio Combined Statistics.

## 2. Performance & Speed Optimization
Matrix recalculations have been optimized to handle large datasets (1.6GB+ SQLite DB) without hanging.

*   **Scan Volume Reduction**: By pre-filtering accounts in the `recent_accounts` CTE, the system avoids calculating expensive monthly persistence scores for inactive accounts. This reduced scan volume by approximately **90%**.
*   **Average Latency**:
    *   **Classic Mode**: ~2.6s (Previously 15s+)
    *   **Persistence Mode**: ~5.7s (Previously 25s+)
*   **Observability**: Added backend timing logs (`[MATRIX] ... calculation took X.XXs`) to monitor performance in production.

## 3. UI Enhancements
To improve clarity, the Recommendation Matrix now includes better documentation of account health.

*   **Status Legend**: A legend has been added to the "Using this screen" info box defining the meaning of the colored dots:
    *   🟢 **Stable**: Healthy Performance
    *   🟡 **Drifting**: Minor Performance Variance
    *   🔴 **Critical**: Severe Performance Degradation
    *   🔵 **New / Stale**: No Data in Last 30 Days (Physically excluded from results)
*   **Consistency**: Ensured all modes use the same dot logic for performance drift monitoring.

## 4. Technical Implementation Notes
*   **Date Functions**: Standardized on native SQLite `date('now', '-30 days')` to avoid timezone and format discrepancies between Python and the database.
*   **Cache Management**: Implemented a server-side cache flush protocol upon restart to ensure stale memory objects are cleared when logic updates occur.

---
*Date of Implementation: April 9, 2026*
