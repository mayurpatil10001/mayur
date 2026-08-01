import json, re
from collections import Counter

cp = json.load(open('.gfre_checkpoint.json'))
done = cp['completed_files']
print(f'Checkpoint: {len(done)} files recorded')
s = cp['stats']
print(f'Stats: fills={s["total_raw_fills"]:,}  ghosts={s["total_ghost_fills"]:,}  trades={s["total_clean_trades"]:,}  flagged={s["flagged_files"]}')

DATE_RE = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')
done_accts = Counter()
for f in done:
    m = DATE_RE.match(f)
    if m:
        done_accts[m.group(2)] += 1

print(f'\nDone accounts ({len(done_accts)}):')
for acct, cnt in sorted(done_accts.items())[:20]:
    print(f'  {acct:<35} {cnt:>4} files')
