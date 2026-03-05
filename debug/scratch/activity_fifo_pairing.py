"""
Build trades from ACTIVITY list (Fills only) using FIFO in TransDateTime order.
Compare to SC Trade List to see if SC uses FIFO (then binary FIFO can match).
"""
import csv
import datetime as dt
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
ACTIVITY = ROOT / "1218 nq all activity list.txt"
TRADES = ROOT / "1218 nq trade list.txt"

def parse_dt(s):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d  %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s[:26] if "." in s else s[:19], fmt.replace("  ", " ").replace(".%f", ".%f")[:len(fmt)])
        except ValueError:
            continue
    return None

# Load activity Fills (Filled, sim16, 12/18)
fills = []
with ACTIVITY.open("r", encoding="utf-8", errors="replace") as f:
    r = csv.DictReader(f, delimiter="\t")
    for row in r:
        if (row.get("ActivityType") or "").strip() != "Fills":
            continue
        if (row.get("OrderStatus") or "").strip() != "Filled":
            continue
        if "sim16" not in (row.get("TradeAccount") or "").lower():
            continue
        td = (row.get("TransDateTime") or row.get("DateTime") or "").strip()
        t = parse_dt(td)
        if not t or t.date().isoformat() != "2025-12-18":
            continue
        try:
            price = float((row.get("FillPrice") or 0) or 0)
            qty = int(float((row.get("FilledQuantity") or 0) or 0))
        except (TypeError, ValueError):
            continue
        side = (row.get("BuySell") or "").strip().upper()
        if side not in ("BUY", "SELL"):
            continue
        oc = (row.get("OpenClose") or "").strip().upper()
        oid = (row.get("InternalOrderID") or "").strip()
        fills.append({
            "ts": t,
            "price": price,
            "qty": qty,
            "side": side,
            "oc": oc,
            "oid": oid,
        })

fills.sort(key=lambda x: (x["ts"], x["oid"]))

# FIFO pairing by (account, symbol) - we have one symbol NQH26
buys = []  # list of {ts, price, qty, oid}
sells = []
trades = []
for f in fills:
    qty, side, price, ts, oc, oid = f["qty"], f["side"], f["price"], f["ts"], f["oc"], f["oid"]
    is_buy = side in ("BUY", "LONG")
    if oc == "OPEN":
        if is_buy:
            buys.append({"ts": ts, "price": price, "qty": qty, "oid": oid})
        else:
            sells.append({"ts": ts, "price": price, "qty": qty, "oid": oid})
        continue
    if oc != "CLOSE":
        continue
    if is_buy:
        # Buy close: consume from sells. Try FIFO (index 0) or LIFO (index -1)
        while qty > 0 and sells:
            s = sells[0]  # FIFO
            mq = min(qty, s["qty"])
            trades.append({
                "entry_dt": s["ts"],
                "exit_dt": ts,
                "entry_price": s["price"],
                "exit_price": price,
                "qty": mq,
                "side": "Short",
            })
            qty -= mq
            s["qty"] -= mq
            if s["qty"] <= 0:
                sells.pop(0)
    else:
        while qty > 0 and buys:
            b = buys[0]  # FIFO
            mq = min(qty, b["qty"])
            trades.append({
                "entry_dt": b["ts"],
                "exit_dt": ts,
                "entry_price": b["price"],
                "exit_price": price,
                "qty": mq,
                "side": "Long",
            })
            qty -= mq
            b["qty"] -= mq
            if b["qty"] <= 0:
                buys.pop(0)

# Load SC trade list
def load_sc(path):
    out = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            if not row.get("Symbol") or "sim16" not in (row.get("Account") or "").lower():
                continue
            ed = parse_dt((row.get("Entry DateTime") or "").replace(" BP", "").replace(" EP", ""))
            xd = parse_dt((row.get("Exit DateTime") or "").replace(" BP", "").replace(" EP", ""))
            if not ed or not xd:
                continue
            if ed.date().isoformat() != "2025-12-18":
                continue
            try:
                ep = float(row.get("Entry Price", 0) or 0)
                xp = float(row.get("Exit Price", 0) or 0)
                q = int(float(row.get("Trade Quantity", 0) or 0))
            except (TypeError, ValueError):
                continue
            side = "Short" if "short" in (row.get("Trade Type") or "").lower() else "Long"
            out.append({"entry_dt": ed, "exit_dt": xd, "entry_price": ep, "exit_price": xp, "qty": q, "side": side})
    return out

sc_trades = load_sc(TRADES)

def match(a, b, tol_sec=5, tol_price=0.5):
    if a["side"] != b["side"] or a["qty"] != b["qty"]:
        return False
    if abs((a["entry_dt"] - b["entry_dt"]).total_seconds()) > tol_sec:
        return False
    if abs((a["exit_dt"] - b["exit_dt"]).total_seconds()) > tol_sec:
        return False
    if abs(a["entry_price"] - b["entry_price"]) > tol_price:
        return False
    if abs(a["exit_price"] - b["exit_price"]) > tol_price:
        return False
    return True

m = sum(1 for at in trades if any(match(at, st) for st in sc_trades))
print("Activity fills:", len(fills))
print("Activity OPEN count:", sum(1 for f in fills if f["oc"] == "OPEN"))
print("Activity CLOSE count:", sum(1 for f in fills if f["oc"] == "CLOSE"))
print("Trades from activity FIFO:", len(trades))
print("SC trade list count:", len(sc_trades))
print("Match (activity FIFO vs SC trade list):", m, "/", len(trades), "=", round(m / len(trades) * 100, 2) if trades else 0, "%")
