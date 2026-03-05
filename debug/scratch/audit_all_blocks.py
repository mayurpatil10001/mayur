from collections import defaultdict
import glob
import os
import re

def audit_clipping():
    with open("logs/import_clipping.log", "r") as f:
        lines = f.readlines()
    
    vsim_blocks = [l for l in lines if "V_SIM16 NQ | DRIFT BLOCKED" in l]
    print(f"Total V_SIM16 DRIFT BLOCKED lines: {len(vsim_blocks)}")
    
    # Extract dates
    date_counts = defaultdict(int)
    for l in vsim_blocks:
        m = re.search(r"\[(\d{4}-\d{2}-\d{2})T", l)
        if m:
            date_counts[m.group(1)] += 1
            
    print("Top 10 days by drift blocks:")
    for d, c in sorted(date_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"{d}: {c} drift blocks")

audit_clipping()
