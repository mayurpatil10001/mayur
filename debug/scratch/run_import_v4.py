import requests
import time

API = "http://localhost:8000"

# Trigger import for V_SIM16
print("Starting import for V_SIM16...")
resp = requests.post(f"{API}/api/system/import-start", json={
    "paths": [r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"],
    "accounts": ["V_SIM16"]
})
print(f"Start response: {resp.status_code} {resp.json()}")

# Poll status
while True:
    time.sleep(5)
    status = requests.get(f"{API}/api/system/import-status").json()
    msg = status.get("message", "")
    running = status.get("running", False)
    print(f"  [{time.strftime('%H:%M:%S')}] Running={running} | {msg}")
    
    if not running:
        print("\n=== FINAL STATS ===")
        stats = status.get("stats", {})
        for k, v in stats.items():
            if k != "breakdown":
                print(f"  {k}: {v}")
        
        # Show breakdown for V_SIM16
        bd = stats.get("breakdown", {})
        for acc, cats in bd.items():
            if "SIM16" in acc.upper():
                print(f"\n  --- {acc} ---")
                for cat, vals in cats.items():
                    print(f"    {cat}: {vals}")
        break
