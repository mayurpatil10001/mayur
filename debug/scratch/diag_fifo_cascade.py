"""Simplified diagnostic - writes clean line-by-line output."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone, SYMBOL_METADATA
import trading_platform.services.binary_log_parser as blp
import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

NY_TZ = ZoneInfo("America/New_York")
TARGET = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

out = []
def p(s=""): out.append(str(s))

def fmt_ny(ts):
    try:
        dt = datetime.datetime.fromisoformat(ts)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(NY_TZ).strftime("%H:%M:%S")
    except: return ts[:8]

def run_fifo(fills):
    groups = defaultdict(list)
    for f in fills:
        groups[(_get_base_symbol_standalone(f['symbol']),)].append(f)
    trades, unp = [], 0
    for _, group in groups.items():
        meta = SYMBOL_METADATA.get("NQ", {"multiplier": 20, "comm": 4.20})
        mul, cpl = meta['multiplier'], meta['comm']/2.0
        group.sort(key=lambda x: x.get('ts_val', 0))
        seen = set()
        dd = []
        for f in group:
            sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
            if sig not in seen: dd.append(f); seen.add(sig)
        buys, sells = [], []
        last_sd = None
        for f in dd:
            q, si, px, ts = f['quantity'], f['side'], f['price'], f['timestamp']
            try:
                dt = datetime.datetime.fromisoformat(ts)
                if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
                ny = dt.astimezone(NY_TZ)
                sd = (ny+datetime.timedelta(days=1)).date() if ny.hour>=17 else ny.date()
            except: sd = None
            if last_sd and sd and sd != last_sd:
                unp += sum(b['q'] for b in buys)+sum(s['q'] for s in sells)
                buys, sells = [], []
            last_sd = sd
            if si in ('BUY','LONG'):
                while q>0 and sells:
                    s=sells[0]; mq=min(q,s['q'])
                    pnl=(s['px']-px)*mq*mul; tc=round(mq*cpl*2,2)
                    trades.append({"s":"SHORT","et":s['t'],"xt":ts,"ep":s['px'],"xp":px,"q":mq,"pnl":round(pnl-tc,2),"ghost":f.get('is_ghost',False)})
                    q-=mq; s['q']-=mq
                    if s['q']<=0: sells.pop(0)
                if q>0: buys.append({"q":q,"px":px,"t":ts})
            else:
                while q>0 and buys:
                    b=buys[0]; mq=min(q,b['q'])
                    pnl=(px-b['px'])*mq*mul; tc=round(mq*cpl*2,2)
                    trades.append({"s":"LONG","et":b['t'],"xt":ts,"ep":b['px'],"xp":px,"q":mq,"pnl":round(pnl-tc,2),"ghost":f.get('is_ghost',False)})
                    q-=mq; b['q']-=mq
                    if b['q']<=0: buys.pop(0)
                if q>0: sells.append({"q":q,"px":px,"t":ts})
        unp += sum(b['q'] for b in buys)+sum(s['q'] for s in sells)
    return trades, unp

# Parse with ghost filter
fills_ok, gc = _parse_file_nitro(TARGET, target_sym="NQ")
p(f"Fills after ghost filter: {len(fills_ok)}")
p(f"Ghosts removed: {sum(gc.values())}")

# Parse without ghost filter
orig = blp._is_ghost_fill
blp._is_ghost_fill = lambda a,n,t: False
fills_all, _ = _parse_file_nitro(TARGET, target_sym="NQ")
blp._is_ghost_fill = orig
p(f"Fills without ghost filter: {len(fills_all)}")
p(f"Ghost fills: {len(fills_all)-len(fills_ok)}")

# Tag ghosts
fsigs = set()
for f in fills_ok:
    fsigs.add((round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity']))
ghosts = []
for f in fills_all:
    sig = (round(f.get('ts_val',0)*2)/2.0, f['price'], f['side'], f['quantity'])
    f['is_ghost'] = sig not in fsigs
    if f['is_ghost']: ghosts.append(f)
ghosts.sort(key=lambda x: x.get('ts_val',0))

p()
p("=== GHOST FILLS (first 20) ===")
for i,g in enumerate(ghosts[:20]):
    p(f"  [{i:>2}] NY={fmt_ny(g['timestamp'])} {g['side']:4s} qty={g['quantity']} px={g['price']:.2f} note='{g.get('note','')[:30]}'")

# FIFO
t1, u1 = run_fifo(fills_ok)
t2, u2 = run_fifo(fills_all)
p()
p(f"No ghosts: {len(t1)} trades, {u1} unpaired")
p(f"W/ ghosts: {len(t2)} trades, {u2} unpaired")

# Side by side
p()
p("=== SIDE BY SIDE (first 30) ===")
p(f"{'#':>3} | {'NO GHOST':^44} | {'WITH GHOST':^44} | OK?")
for i in range(min(30, max(len(t1),len(t2)))):
    l = t1[i] if i<len(t1) else None
    r = t2[i] if i<len(t2) else None
    ls = f"{fmt_ny(l['et'])} {l['s']:>5} {l['ep']:>9.2f} {l['xp']:>9.2f} {l['pnl']:>+10.2f}" if l else "---"
    rs = f"{fmt_ny(r['et'])} {r['s']:>5} {r['ep']:>9.2f} {r['xp']:>9.2f} {r['pnl']:>+10.2f}" if r else "---"
    if r and r.get('ghost'): rs += " [G]"
    ok = "Y" if (l and r and abs(l['pnl']-r['pnl'])<0.01) else "N"
    p(f"{i+1:>3} | {ls} | {rs} | {ok}")

# Divergence
p()
p("=== DIVERGENCE POINT ===")
for i in range(min(len(t1),len(t2))):
    if abs(t1[i]['pnl']-t2[i]['pnl'])>0.01:
        p(f"First mismatch at trade #{i+1}")
        p(f"  No ghost: {fmt_ny(t1[i]['et'])} {t1[i]['s']} ep={t1[i]['ep']:.2f} xp={t1[i]['xp']:.2f} pnl={t1[i]['pnl']:+.2f}")
        p(f"  W/ ghost: {fmt_ny(t2[i]['et'])} {t2[i]['s']} ep={t2[i]['ep']:.2f} xp={t2[i]['xp']:.2f} pnl={t2[i]['pnl']:+.2f}")
        # Show ghosts before this point
        try:
            cutoff = datetime.datetime.fromisoformat(t2[i]['et']).replace(tzinfo=datetime.timezone.utc).timestamp()
        except: cutoff = 9e15
        p(f"  Ghost fills before this trade:")
        for g in ghosts:
            if g.get('ts_val',0) <= cutoff+1:
                p(f"    NY={fmt_ny(g['timestamp'])} {g['side']:4s} qty={g['quantity']} px={g['price']:.2f}")
        break
else:
    p("No divergence found!")

# Write
with open("diag_result.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out))
print(f"Done. Written to diag_result.txt ({len(out)} lines)")
