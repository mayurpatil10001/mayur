"""
import_and_compare_tm7.py
=========================
1. Parses the RAR Activity Log using the PROJECT'S EXACT _pairs_by_open_close logic
   (same multiplier, same commission, same side detection as trade_import_service.py)
2. Writes results to a temp table  `rar_trades`  in trading_platform.db
3. Runs a full side-by-side comparison against existing  processed_trades  for TM_7/NQ
4. Prints a detailed report with matched/unmatched trades + statistics
"""

import sys, io, csv, sqlite3, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import datetime, timedelta
from collections import defaultdict, deque
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────────
RAR_FILE   = r"c:\SC_results_WF\rar_extract\example tm7 NQU26 2026-07-20.txt"
DB_PATH    = r"c:\SC_results_WF\trading_platform.db"
ACCOUNT    = "TM_7"

# Exact same values as SYMBOL_METADATA in binary_log_parser.py
SYMBOL_META = {
    "NQ":  {"multiplier": 20,  "comm": 4.20},
    "MNQ": {"multiplier": 2,   "comm": 1.00},
    "ES":  {"multiplier": 50,  "comm": 4.20},
    "MES": {"multiplier": 5,   "comm": 1.00},
}

def base_symbol(raw: str) -> str:
    s = raw.upper()
    for k in SYMBOL_META:
        if s.startswith(k):
            return k
    return s[:2] if len(s) >= 2 else s

# ── STEP 1: Parse Activity Log fills ──────────────────────────────────────────
def parse_activity_fills(filepath: str):
    """
    Reads Sierra Chart 'All Activity' tab-delimited export.
    Extracts only ActivityType=Fills rows for ACCOUNT / NQ symbols.
    Returns list of fill dicts in project's internal format.
    """
    fills = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if (row.get("ActivityType") or "").strip() != "Fills":
                continue
            acct = (row.get("TradeAccount") or "").strip()
            if acct != ACCOUNT:
                continue
            sym_raw = (row.get("Symbol") or "").strip()
            if not sym_raw.upper().startswith("NQ"):
                continue
            side_raw = (row.get("BuySell") or "").strip().upper()
            if side_raw not in ("BUY", "SELL"):
                continue

            try:
                fp = float(row.get("FillPrice") or 0)
                fq = int(float(row.get("FilledQuantity") or 0))
            except:
                continue
            if fp == 0 or fq == 0:
                continue

            dt_str = (row.get("DateTime") or "").strip()
            try:
                dt = datetime.strptime(dt_str[:26], "%Y-%m-%d  %H:%M:%S.%f")
            except:
                try:
                    dt = datetime.strptime(dt_str[:19], "%Y-%m-%d  %H:%M:%S")
                except:
                    continue

            oc = (row.get("OpenClose") or "").strip().upper()
            ioid = (row.get("InternalOrderID") or "").strip()
            parent = (row.get("ParentInternalOrderID") or "").strip()

            fills.append({
                "account_name":   acct,
                "symbol":         sym_raw,
                "side":           side_raw,        # BUY / SELL
                "price":          fp,
                "quantity":       fq,
                "timestamp":      dt,
                "ts_val":         dt.timestamp(),
                "offset":         0,
                "open_close":     oc,               # OPEN / CLOSE
                "internal_order_id": ioid,
                "parent_order_id":   parent,
            })

    fills.sort(key=lambda x: x["ts_val"])
    return fills


# ── STEP 2: Project's exact pairing logic (copied from trade_import_service.py) ─
def pairs_by_open_close(fills):
    """
    Exact replica of TradeImportService._pairs_by_open_close().
    Uses ParentInternalOrderID when available, falls back to FIFO.
    """
    groups = defaultdict(list)
    for f in fills:
        key = (f["account_name"], f["symbol"])
        groups[key].append(f)

    all_trades = []
    unpaired_total = 0

    for (acc, sym), group in groups.items():
        group.sort(key=lambda x: (x.get("ts_val", 0), x.get("offset", 0)))
        bsym = base_symbol(sym)
        meta = SYMBOL_META.get(bsym, {"multiplier": 1, "comm": 4.20})
        mult        = meta["multiplier"]
        comm_per_leg = meta["comm"] / 2.0

        opens      = {}   # oid -> [{"fill": f, "qty_left": n}, ...]
        opens_fifo = []   # same entries in insertion order for FIFO fallback

        for f in group:
            oc     = (f.get("open_close") or "").upper()
            oid    = (f.get("internal_order_id") or "").strip()
            parent = (f.get("parent_order_id") or "").strip()

            if oc == "OPEN" and oid:
                if oid not in opens:
                    opens[oid] = []
                entry = {"fill": f, "qty_left": f["quantity"]}
                opens[oid].append(entry)
                opens_fifo.append(entry)

            elif oc == "CLOSE":
                close_qty = f["quantity"]
                matched   = False

                # --- Primary: match by ParentInternalOrderID ---
                if parent and parent in opens and opens[parent]:
                    entry_list = opens[parent]
                    while close_qty > 0 and entry_list:
                        o = entry_list[0]
                        mq = min(close_qty, o["qty_left"])
                        if mq <= 0:
                            entry_list.pop(0)
                            continue
                        of      = o["fill"]
                        of_side = (of.get("side") or "").upper()
                        pnl = ((f["price"] - of["price"]) * mq * mult
                               if of_side in ("BUY", "LONG")
                               else (of["price"] - f["price"]) * mq * mult)
                        comm  = round(mq * comm_per_leg * 2, 2)
                        side  = "LONG" if of_side in ("BUY", "LONG") else "SHORT"
                        all_trades.append({
                            "account":      acc,
                            "symbol":       bsym,
                            "side":         side,
                            "entry_time":   of["timestamp"],
                            "exit_time":    f["timestamp"],
                            "entry_price":  of["price"],
                            "exit_price":   f["price"],
                            "quantity":     int(mq),
                            "profit_loss":  round(pnl - comm, 2),
                            "commission":   comm,
                        })
                        o["qty_left"] -= mq
                        close_qty     -= mq
                        if o["qty_left"] <= 0:
                            entry_list.pop(0)
                        matched = True
                    if not opens.get(parent):
                        opens.pop(parent, None)

                # --- Fallback: FIFO ---
                if close_qty > 0 and opens_fifo:
                    f_side_upper = (f.get("side") or "").upper()
                    want_open    = "SELL" if f_side_upper in ("BUY", "LONG") else "BUY"
                    i = 0
                    while close_qty > 0 and i < len(opens_fifo):
                        o      = opens_fifo[i]
                        of     = o["fill"]
                        of_side = (of.get("side") or "").upper()
                        if o["qty_left"] <= 0 or of_side != want_open:
                            i += 1
                            continue
                        mq    = min(close_qty, o["qty_left"])
                        pnl   = ((f["price"] - of["price"]) * mq * mult
                                 if of_side in ("BUY", "LONG")
                                 else (of["price"] - f["price"]) * mq * mult)
                        comm  = round(mq * comm_per_leg * 2, 2)
                        side  = "LONG" if of_side in ("BUY", "LONG") else "SHORT"
                        all_trades.append({
                            "account":      acc,
                            "symbol":       bsym,
                            "side":         side,
                            "entry_time":   of["timestamp"],
                            "exit_time":    f["timestamp"],
                            "entry_price":  of["price"],
                            "exit_price":   f["price"],
                            "quantity":     int(mq),
                            "profit_loss":  round(pnl - comm, 2),
                            "commission":   comm,
                        })
                        o["qty_left"] -= mq
                        close_qty     -= mq
                        matched = True
                        if o["qty_left"] <= 0:
                            opens_fifo.pop(i)
                        else:
                            i += 1
                    if close_qty > 0:
                        unpaired_total += close_qty
                elif close_qty > 0 and not matched:
                    unpaired_total += close_qty

        opens_fifo[:] = [o for o in opens_fifo if o["qty_left"] > 0]
        unpaired_total += sum(o["qty_left"] for o in opens_fifo)
        unpaired_total += sum(sum(e["qty_left"] for e in v) for v in opens.values())

    return all_trades, unpaired_total


# ── STEP 3: Write parsed RAR trades to temp table ──────────────────────────────
def write_rar_to_db(conn, rar_trades):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS rar_trades")
    cur.execute("""
        CREATE TABLE rar_trades (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            account      TEXT,
            symbol       TEXT,
            side         TEXT,
            entry_time   TEXT,
            exit_time    TEXT,
            entry_price  REAL,
            exit_price   REAL,
            quantity     INTEGER,
            profit_loss  REAL,
            commission   REAL
        )
    """)
    for t in rar_trades:
        cur.execute("""
            INSERT INTO rar_trades
              (account, symbol, side, entry_time, exit_time,
               entry_price, exit_price, quantity, profit_loss, commission)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            t["account"], t["symbol"], t["side"],
            t["entry_time"].isoformat(), t["exit_time"].isoformat(),
            t["entry_price"], t["exit_price"],
            t["quantity"], t["profit_loss"], t["commission"],
        ))
    conn.commit()
    print(f"  Written {len(rar_trades):,} RAR trades to table 'rar_trades'")


# ── STEP 4: Load DB trades for TM_7/NQ ────────────────────────────────────────
def load_db_trades(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT account_name, symbol, side, entry_time, exit_time,
               entry_price, exit_price, quantity, profit_loss, commission
        FROM processed_trades
        WHERE account_name = 'TM_7' AND symbol LIKE 'NQ%'
        ORDER BY entry_time
    """)
    return [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]


# ── STEP 5: Match trades ───────────────────────────────────────────────────────
def match_trades(rar_trades, db_trades, window_sec=5):
    """Match by date + entry_price ± 0.5 + direction within window_sec."""
    db_by_date = defaultdict(list)
    for i, t in enumerate(db_trades):
        key = (t["entry_time"] or "")[:10]
        db_by_date[key].append((i, t))

    db_used   = set()
    matched   = []
    rar_only  = []

    for rt in rar_trades:
        date_key = rt["entry_time"].strftime("%Y-%m-%d")
        cands    = db_by_date.get(date_key, [])
        best, best_dt = None, timedelta(seconds=window_sec)

        for idx, dbt in cands:
            if idx in db_used:
                continue
            try:
                db_dt = datetime.fromisoformat(dbt["entry_time"])
            except:
                continue
            td = abs(rt["entry_time"] - db_dt)
            pd = abs(rt["entry_price"] - float(dbt["entry_price"] or 0))
            rar_s = "LONG" if rt["side"] == "LONG" else "SHORT"
            db_s  = (dbt.get("side") or "").upper()
            if td <= best_dt and pd <= 0.5 and (rar_s == db_s or db_s == ""):
                best_dt, best = td, idx

        if best is not None:
            db_used.add(best)
            matched.append({"rar": rt, "db": db_trades[best]})
        else:
            rar_only.append(rt)

    db_only = [t for i, t in enumerate(db_trades) if i not in db_used]
    return matched, rar_only, db_only


# ── STEP 6: Stats helpers ──────────────────────────────────────────────────────
def stats(pnls):
    if not pnls:
        return {}
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gw     = sum(wins)   or 0
    gl     = abs(sum(losses)) or 1
    return {
        "n":   len(pnls),
        "tot": round(sum(pnls), 2),
        "avg": round(sum(pnls) / len(pnls), 2),
        "wr":  round(len(wins) / len(pnls) * 100, 1),
        "pf":  round(gw / gl, 2),
        "aw":  round(gw / max(len(wins), 1), 2),
        "al":  round(sum(losses) / max(len(losses), 1), 2),
        "best":  max(pnls),
        "worst": min(pnls),
    }


# ── STEP 7: Full Report ────────────────────────────────────────────────────────
def report(rar_trades, db_trades, matched, rar_only, db_only):
    SEP  = "=" * 90
    LINE = "-" * 90

    rar_pnls = [t["profit_loss"] for t in rar_trades]
    db_pnls  = [float(t["profit_loss"] or 0) for t in db_trades]
    rs = stats(rar_pnls)
    ds = stats(db_pnls)

    # --- date ranges ---
    rar_dates = sorted(t["entry_time"] for t in rar_trades)
    db_dates  = sorted(t["entry_time"] for t in db_trades)
    rar_start = rar_dates[0].date()  if rar_dates else "?"
    rar_end   = rar_dates[-1].date() if rar_dates else "?"
    db_start  = (db_dates[0][:10])   if db_dates  else "?"
    db_end    = (db_dates[-1][:10])  if db_dates  else "?"

    print(f"\n{SEP}")
    print("  IMPORT & COMPARE REPORT | TM_7 / NQ")
    print("  Parsing method: project's _pairs_by_open_close (ParentID + FIFO fallback)")
    print(SEP)

    print(f"\n  DATE RANGES")
    print(f"  {'Source':<24} {'From':<14} {'To':<14} {'Trades':>8}")
    print(f"  {'-'*24} {'-'*14} {'-'*14} {'-'*8}")
    print(f"  {'RAR File (just parsed)':<24} {str(rar_start):<14} {str(rar_end):<14} {rs.get('n',0):>8,}")
    print(f"  {'Database (TM_7/NQ)':<24} {str(db_start):<14} {str(db_end):<14} {ds.get('n',0):>8,}")

    # Overlap
    overlap = False
    try:
        if datetime.strptime(str(rar_start), "%Y-%m-%d") <= datetime.strptime(db_end, "%Y-%m-%d"):
            overlap = True
    except:
        pass

    print(f"\n  DATE OVERLAP: {'YES - matching possible' if overlap else 'NO - completely different periods'}")
    if not overlap:
        gap_days = (datetime.strptime(str(rar_start), "%Y-%m-%d") - datetime.strptime(db_end, "%Y-%m-%d")).days
        print(f"  Gap between RAR start and last DB trade: {gap_days} days")

    # Match summary
    match_pct = len(matched) / max(rs.get("n", 1), 1) * 100
    print(f"\n  MATCH SUMMARY")
    print(f"  {'Metric':<40} {'Count':>10}")
    print(f"  {'-'*40} {'-'*10}")
    print(f"  {'Matched (same entry time + price + dir)':<40} {len(matched):>10,}")
    print(f"  {'RAR only (not in DB)':<40} {len(rar_only):>10,}")
    print(f"  {'DB only (not in RAR)':<40} {len(db_only):>10,}")
    print(f"  {'Match Rate':<40} {match_pct:>9.1f}%")

    # Performance comparison
    print(f"\n  PERFORMANCE COMPARISON (project's pairing logic applied to both)")
    print(f"  {'Metric':<30} {'RAR (parsed)':>14} {'Database':>14} {'Diff':>14}")
    print(f"  {'-'*30} {'-'*14} {'-'*14} {'-'*14}")

    def row(label, rk, dk, fmt=".2f", pct=False, dollar=False):
        rv = rs.get(rk)
        dv = ds.get(dk)
        if rv is None or dv is None:
            print(f"  {label:<30} {'N/A':>14} {'N/A':>14} {'N/A':>14}")
            return
        diff = rv - dv
        sfx = "%" if pct else ""
        if dollar:
            print(f"  {label:<30} {rv:>13,.2f} {dv:>13,.2f} {diff:>+13,.2f}")
        elif pct:
            print(f"  {label:<30} {rv:>13.1f}% {dv:>13.1f}% {diff:>+13.1f}%")
        else:
            print(f"  {label:<30} {rv:>14{fmt}} {dv:>14{fmt}} {diff:>+14{fmt}}")

    row("Total Trades",        "n",    "n",    fmt="d")
    row("Total PnL ($)",       "tot",  "tot",  dollar=True)
    row("Avg Trade ($)",       "avg",  "avg",  dollar=True)
    row("Win Rate",            "wr",   "wr",   pct=True)
    row("Profit Factor",       "pf",   "pf",   fmt=".2f")
    row("Avg Winner ($)",      "aw",   "aw",   dollar=True)
    row("Avg Loser ($)",       "al",   "al",   dollar=True)
    row("Best Trade ($)",      "best", "best", dollar=True)
    row("Worst Trade ($)",     "worst","worst",dollar=True)

    # Matched trade detail
    if matched:
        print(f"\n  MATCHED TRADES (first 30) - side-by-side verification")
        print(f"  {'#':<4} {'Entry Time':<20} {'Dir':<5} {'Qty':<4} "
              f"{'RAR Entry':>9} {'DB Entry':>9} "
              f"{'RAR PnL':>10} {'DB PnL':>10} {'Diff':>9} Status")
        print(f"  {'-'*4} {'-'*20} {'-'*5} {'-'*4} {'-'*9} {'-'*9} {'-'*10} {'-'*10} {'-'*9} {'-'*8}")
        exact = price_diff = pnl_diff_count = 0
        for i, m in enumerate(matched[:30], 1):
            r, d  = m["rar"], m["db"]
            dp    = abs(r["entry_price"] - float(d["entry_price"] or 0))
            pp    = round(r["profit_loss"] - float(d["profit_loss"] or 0), 2)
            status = "EXACT" if dp < 0.01 and abs(pp) < 0.01 else ("PRICE?" if dp >= 0.01 else "PNL?")
            if status == "EXACT": exact += 1
            elif "PRICE" in status: price_diff += 1
            else: pnl_diff_count += 1
            print(f"  {i:<4} {str(r['entry_time'])[:19]:<20} "
                  f"{r['side'][:5]:<5} {r['quantity']:<4} "
                  f"{r['entry_price']:>9.2f} {float(d['entry_price'] or 0):>9.2f} "
                  f"{r['profit_loss']:>10.2f} {float(d['profit_loss'] or 0):>10.2f} "
                  f"{pp:>+9.2f} {status}")

        # Stats on all matched
        all_diffs = [round(m["rar"]["profit_loss"] - float(m["db"]["profit_loss"] or 0), 2) for m in matched]
        exact_all = sum(1 for d in all_diffs if abs(d) < 0.01)
        print(f"\n  All {len(matched)} matched trades:")
        print(f"    Exact matches (PnL diff < $0.01): {exact_all} ({exact_all/len(matched)*100:.1f}%)")
        print(f"    Avg PnL difference:               ${sum(abs(d) for d in all_diffs)/len(all_diffs):.2f}")
        print(f"    Max PnL difference:               ${max(abs(d) for d in all_diffs):.2f}")

    # RAR-only trades sample
    if rar_only:
        print(f"\n  RAR-ONLY TRADES (not in DB) - first 20 of {len(rar_only):,}")
        print(f"  {'#':<4} {'Entry Time':<20} {'Exit Time':<20} {'Dir':<5} "
              f"{'Qty':<4} {'Entry':>9} {'Exit':>9} {'PnL':>10}")
        print(f"  {'-'*4} {'-'*20} {'-'*20} {'-'*5} {'-'*4} {'-'*9} {'-'*9} {'-'*10}")
        for i, t in enumerate(rar_only[:20], 1):
            print(f"  {i:<4} {str(t['entry_time'])[:19]:<20} {str(t['exit_time'])[:19]:<20} "
                  f"{t['side'][:5]:<5} {t['quantity']:<4} "
                  f"{t['entry_price']:>9.2f} {t['exit_price']:>9.2f} {t['profit_loss']:>10.2f}")
        rar_only_pnl = sum(t["profit_loss"] for t in rar_only)
        print(f"\n  Total PnL of RAR-only trades: ${rar_only_pnl:,.2f}")

    # DB-only sample
    if db_only:
        print(f"\n  DB-ONLY TRADES (not in RAR) - first 10 of {len(db_only):,}")
        print(f"  {'Entry Time':<22} {'Dir':<6} {'Qty':<4} {'Entry':>9} {'PnL':>10}")
        print(f"  {'-'*22} {'-'*6} {'-'*4} {'-'*9} {'-'*10}")
        for t in db_only[:10]:
            print(f"  {(t['entry_time'] or '')[:19]:<22} {(t['side'] or '')[:6]:<6} "
                  f"{int(t['quantity'] or 0):<4} {float(t['entry_price'] or 0):>9.2f} "
                  f"{float(t['profit_loss'] or 0):>10.2f}")

    # Daily breakdown for RAR
    print(f"\n  RAR DAILY PnL BREAKDOWN (all {len(rar_trades):,} parsed trades)")
    print(f"  {'Date':<12} {'Trades':>7} {'Win%':>7} {'PnL':>12} {'Cum PnL':>13}")
    print(f"  {'-'*12} {'-'*7} {'-'*7} {'-'*12} {'-'*13}")
    daily = defaultdict(list)
    for t in rar_trades:
        daily[t["entry_time"].date()].append(t["profit_loss"])
    cum = 0
    for d in sorted(daily):
        pnls = daily[d]
        wins = sum(1 for p in pnls if p > 0)
        tot  = sum(pnls)
        cum += tot
        print(f"  {str(d):<12} {len(pnls):>7} {wins/len(pnls)*100:>6.1f}% {tot:>12,.2f} {cum:>13,.2f}")

    # Symbol breakdown
    print(f"\n  BY CONTRACT SYMBOL")
    print(f"  {'Symbol':<10} {'Trades':>7} {'Win%':>7} {'Total PnL':>13} {'Avg/Trade':>12}")
    print(f"  {'-'*10} {'-'*7} {'-'*7} {'-'*13} {'-'*12}")
    sym_data = defaultdict(list)
    for t in rar_trades:
        sym_data[t["symbol"]].append(t["profit_loss"])
    for sym in sorted(sym_data):
        pl = sym_data[sym]
        wn = sum(1 for p in pl if p > 0)
        tt = sum(pl)
        print(f"  {sym:<10} {len(pl):>7} {wn/len(pl)*100:>6.1f}% {tt:>13,.2f} {tt/len(pl):>12,.2f}")

    # Final verdict
    print(f"\n{SEP}")
    print("  FINAL VERDICT")
    print(SEP)
    print(f"  Parsing method: Project's _pairs_by_open_close (identical to DB import logic)")
    print(f"  RAR trades parsed:  {rs.get('n',0):,}  (using ParentInternalOrderID + FIFO fallback)")
    print(f"  DB trades loaded:   {ds.get('n',0):,}")
    print(f"  Match rate:         {match_pct:.1f}%")
    print()
    if not overlap:
        print(f"  DATE GAP: The RAR file covers {rar_start} to {rar_end}.")
        print(f"  The DB ends at {db_end}. These are COMPLETELY separate periods.")
        print(f"  => The {rs.get('n',0):,} RAR trades are NEW and NOT yet in the database.")
    print()
    # Performance verdict
    rr = rs.get("tot", 0); dr = ds.get("tot", 0)
    rw = rs.get("wr",  0); dw = ds.get("wr",  0)
    if rr < 0 and dr < 0:
        trend = "WORSE" if rr < dr else "SLIGHTLY BETTER"
        print(f"  STRATEGY HEALTH: LOSING in BOTH periods. 2026 period is {trend}.")
        print(f"  RAR PnL ${rr:,.0f}  vs  DB PnL ${dr:,.0f}  |  Win rate {rw}% vs {dw}%")
    elif rr > 0:
        print(f"  STRATEGY HEALTH: 2026 period is PROFITABLE. PnL ${rr:,.0f}, Win rate {rw}%")
    print()
    print(f"  RECOMMENDATION:")
    print(f"    - Import the RAR file via the platform's trade import service")
    print(f"    - Then run time-bin analysis to find which specific hours/days")
    print(f"      within TM_7/NQ have a positive edge")
    print(SEP)


# ── MAIN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    SEP = "=" * 90
    print(f"\n{SEP}")
    print("  TM_7 / NQ — IMPORT & COMPARE  |  RAR file (project logic) vs Database")
    print(SEP)

    print("\n[1/5] Parsing Activity Log fills from RAR file...")
    fills = parse_activity_fills(RAR_FILE)
    print(f"      Fills found: {len(fills):,}")
    
    # Show fill side distribution
    sides = defaultdict(int)
    for f in fills:
        sides[f["open_close"] + "/" + f["side"]] += 1
    for k, v in sorted(sides.items()):
        print(f"      {k}: {v:,}")

    print("\n[2/5] Pairing with project's _pairs_by_open_close logic...")
    rar_trades, unpaired = pairs_by_open_close(fills)
    rar_trades.sort(key=lambda t: t["entry_time"])
    print(f"      Paired trades:  {len(rar_trades):,}")
    print(f"      Unpaired qty:   {unpaired}")

    print("\n[3/5] Writing RAR trades to 'rar_trades' table in DB...")
    conn = sqlite3.connect(DB_PATH)
    write_rar_to_db(conn, rar_trades)

    print("\n[4/5] Loading existing TM_7/NQ trades from processed_trades...")
    db_trades = load_db_trades(conn)
    print(f"      DB trades loaded: {len(db_trades):,}")

    print("\n[5/5] Matching and building report...")
    matched, rar_only, db_only = match_trades(rar_trades, db_trades)
    print(f"      Matched: {len(matched)} | RAR-only: {len(rar_only)} | DB-only: {len(db_only)}")

    report(rar_trades, db_trades, matched, rar_only, db_only)
    conn.close()
