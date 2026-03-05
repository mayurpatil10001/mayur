import re
from collections import Counter

def audit_patterns(path):
    with open(path, "rb") as f:
        data = f.read().decode(errors='ignore')
    
    # Simple regex to find blocks of text that look like messages
    words = re.split(r'\x00+', data)
    msgs = [w.strip() for w in words if len(w) > 5] # Shorter for more breath
    
    interesting = [m for m in msgs if ("buy" in m.lower() or "sell" in m.lower() or "fill" in m.lower() or "order" in m.lower())]
    
    # Normalize by removing numbers
    def normalize(s):
        s = re.sub(r'\d+', 'N', s)
        s = re.sub(r'N:N:N', 'TIME', s)
        s = re.sub(r'N-N-N', 'DATE', s)
        return s[:100]

    counts = Counter(normalize(m) for m in interesting)
    
    print("\nMessage Patterns (Normalized Top 50):")
    for pat, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:50]:
        print(f"  Count: {count:5d} | {pat}")

audit_patterns(r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data")
