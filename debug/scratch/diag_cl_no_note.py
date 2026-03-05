import os
import glob
import sys
import re

# Add the current directory to path
sys.path.append(os.getcwd())

from trading_platform.services.binary_log_parser import _parse_file_nitro

def run_diagnostic():
    base_path = "D:/SierraChart_Simulated_Feed/TradeActivityLogs"
    # Find files matching TM_2, TM_10 or CL
    patterns = ["*TM_2*", "*TM_10*", "*CL*"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(base_path, f"TradeActivityLog_*_{p}.data")))
    
    # Remove duplicates
    files = list(set(files))
    print(f"Total candidate files for TM/CL: {len(files)}")

    tm_stats = {} # acc -> {total_fills, with_note, ghosts}
    cl_ghosts_count = 0
    cl_valid_count = 0

    for fp in files[:500]: # Sample 500 files to be fast
        fn = os.path.basename(fp)
        
        # Determine account from filename
        # Pattern: TradeActivityLog_DATE_UTC.ACCOUNT.data
        acc_name = "UNKNOWN"
        m = re.search(r'\.([^.]+)\.data$', fn, re.I)
        if m:
            acc_name = m.group(1).upper()
        
        try:
            fills, ghosts = _parse_file_nitro(fp)
            
            if acc_name not in tm_stats:
                tm_stats[acc_name] = {"total": 0, "notes": 0, "ghosts": 0}
            
            tm_stats[acc_name]["total"] += len(fills) + len(ghosts)
            tm_stats[acc_name]["notes"] += len(fills)
            tm_stats[acc_name]["ghosts"] += len(ghosts)

            # Check for CL symbol specifically
            all_fills_in_file = fills + ghosts
            for f in all_fills_in_file:
                if "CL" in f.get('symbol', '').upper():
                    # Check if it was in the valid or ghost list
                    is_valid = f in fills
                    if is_valid:
                        cl_valid_count += 1
                    else:
                        cl_ghosts_count += 1
        except Exception as e:
            continue

    print("\n--- CL SESSION STATS ---")
    print(f"Valid CL Fills: {cl_valid_count}")
    print(f"Ghost CL Fills: {cl_ghosts_count}")

    print("\n--- ACCOUNT NOTE DISTRIBUTION ---")
    print(f"{'Account':20} | {'Total':6} | {'Notes':6} | {'Ghosts':6} | {'NoteRate'}")
    print("-" * 60)
    # Sort by NoteRate ascending
    sorted_accs = sorted(tm_stats.keys(), key=lambda x: (tm_stats[x]['notes']/tm_stats[x]['total']) if tm_stats[x]['total']>0 else 0)
    for acc in sorted_accs:
        s = tm_stats[acc]
        if s["total"] > 0:
            rate = (s["notes"] / s["total"]) * 100
            print(f"{acc:20} | {s['total']:6} | {s['notes']:6} | {s['ghosts']:6} | {rate:6.1f}%")

run_diagnostic()
