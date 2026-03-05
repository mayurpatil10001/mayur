"""
Cross-account ghost import matrix: run binary parse on scanner paths from app_settings.json
and report fill/ghost counts per account. Use for regression and cross-account validation.

Run from project root: python tests/run_ghost_import_matrix.py

Optional: place tests/fixtures/ghost_import_expected.json with expected min_fills or
max_ghosts per account to assert no regression.
"""
import glob
import json
import os
import re
import sys

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load_app_settings():
    path = os.path.join(ROOT, "app_settings.json")
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("scanners", [])


def main():
    from trading_platform.services.binary_log_parser import _parse_file_nitro

    scanners = load_app_settings()
    if not scanners:
        print("No scanners in app_settings.json")
        return 0

    # Optional baseline
    fixture_path = os.path.join(ROOT, "tests", "fixtures", "ghost_import_expected.json")
    expected = {}
    if os.path.isfile(fixture_path):
        with open(fixture_path, "r", encoding="utf-8") as f:
            expected = json.load(f)

    paths_seen = set()
    results = []
    errors = []

    for scan in scanners:
        base = scan.get("path")
        if not base or not os.path.isdir(base):
            continue
        pattern = os.path.join(base, "TradeActivityLog_*.data")
        files = glob.glob(pattern) + glob.glob(os.path.join(base, "TradeActivityLog_*.DATA"))
        files = sorted(set(files))[:20]  # Limit per scanner

        for file_path in files:
            if file_path in paths_seen:
                continue
            paths_seen.add(file_path)
            fn = os.path.basename(file_path).upper()
            # Account from filename, e.g. TradeActivityLog_2025-12-18_UTC.V_SIM16.DATA -> V_SIM16
            parts = fn.replace(".DATA", "").replace(".DATA", "").split(".")
            acc = parts[-1] if len(parts) > 1 else "UNKNOWN"
            try:
                fills, ghosts = _parse_file_nitro(file_path, acc_filter=None)
                n_fills = len(fills)
                n_ghosts = len(ghosts)
                results.append({"account": acc, "file": fn, "fills": n_fills, "ghosts": n_ghosts})
                key = acc.upper()
                exp = expected.get(key, {})
                if "min_fills" in exp and n_fills < exp["min_fills"]:
                    errors.append(f"{acc}: fills {n_fills} < min_fills {exp['min_fills']}")
                if "max_ghosts" in exp and n_ghosts > exp.get("max_ghosts", 999999):
                    errors.append(f"{acc}: ghosts {n_ghosts} > max_ghosts {exp['max_ghosts']}")
            except Exception as e:
                errors.append(f"{file_path}: {e}")
                results.append({"account": acc, "file": fn, "fills": -1, "ghosts": -1, "error": str(e)})

    # Report matrix
    print("Account      | Fills | Ghosts | File")
    print("-" * 70)
    for r in results:
        acc = (r["account"] or "?")[:12]
        fills = r.get("fills", "?")
        ghosts = r.get("ghosts", "?")
        fname = (r.get("file") or "?")[:45]
        print(f"{acc:<12} | {fills:>5} | {ghosts:>6} | {fname}")
    if errors:
        print("\nRegressions or errors:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nOK: no regression (or no fixture).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
