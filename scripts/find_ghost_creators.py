"""
scripts/find_ghost_creators.py
==============================
Inspects raw binary files across accounts (TM_7, ES-TM_7, V_sim, etc.) to identify:
1. What component generates ghost fills (Sierra Chart Trade Evaluator vs SC Internal Position Engine vs Manual User Actions)
2. The exact message text, tags, and timestamps of ghost fills
"""

import os
import glob
import re
import struct
from collections import Counter

DATASET_DIR = r"c:\SC_results_WF\dataset"

def inspect_ghosts():
    files = glob.glob(os.path.join(DATASET_DIR, "TradeActivityLog_2026-06-*.data")) + \
            glob.glob(os.path.join(DATASET_DIR, "TradeActivityLog_2024-05-*.data"))

    reasons = Counter()
    sample_records = []

    for fp in files[:30]:
        fn = os.path.basename(fp)
        try:
            with open(fp, "rb") as f:
                d = f.read(50 * 1024 * 1024)
        except:
            continue

        n = len(d)
        pos = 0
        current_note = ""
        current_ts = ""

        while pos + 8 <= n:
            tag, length = struct.unpack("<II", d[pos:pos+8])
            if tag == 0 or tag > 512 or length > 65536:
                pos += 8
                continue

            val_start = pos + 8
            val_end = val_start + length
            if val_end > n:
                break

            val = d[val_start:val_end]

            if tag == 0x66:  # Timestamp
                current_note = ""
                try:
                    v = struct.unpack("<d", val[:8])[0]
                    if 30000 < v < 100000:
                        import datetime
                        current_ts = (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=v)).strftime("%H:%M:%S")
                except:
                    pass

            elif tag == 0x82:  # Order Note
                current_note = val.decode("utf-8", errors="ignore").strip()

            elif tag == 104:  # Message Text
                txt = val.decode("utf-8", errors="ignore")
                txt_l = txt.lower()

                if "trading evaluator" in txt_l and "filled" in txt_l:
                    has_tag = "autotrader_" in txt_l or "text: tag:" in txt_l or bool(current_note)
                    if not has_tag:
                        if "fill based on queue" in txt_l:
                            cat = "Sierra Chart Queue Simulator (Delayed Order Match)"
                        elif "updated internal position" in txt_l:
                            cat = "Sierra Chart Internal Position Engine Reset"
                        elif "bid:" in txt_l:
                            cat = "Sierra Chart Trade Evaluator (Missing C++ DLL Strategy Tag)"
                        else:
                            cat = "Other SC Internal Order Record"

                        reasons[cat] += 1
                        if len(sample_records) < 12:
                            sample_records.append({
                                "file": fn,
                                "time": current_ts,
                                "cat": cat,
                                "note": current_note,
                                "msg": txt[:140],
                            })
            pos = val_end

    print("=" * 70)
    print("WHO / WHAT WAS CREATING GHOST FILLS?")
    print("=" * 70)
    print("\nCategorized Sources of Ghost Fills across Raw Logs:")
    for cat, count in reasons.most_common():
        print(f"  {count:5d} occurrences | {cat}")

    print("\nSample Ghost Records from Raw Binary Stream:")
    for i, rec in enumerate(sample_records, 1):
        print(f" #{i:02d} | File: {rec['file']} | Time: {rec['time']} | Category: {rec['cat']}")
        print(f"      Note: '{rec['note']}' | Msg: {rec['msg']}\n")

if __name__ == "__main__":
    inspect_ghosts()
