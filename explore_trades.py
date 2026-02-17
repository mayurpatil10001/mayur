import re
import os
from pathlib import Path

def dump_trade_related_strings(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Find messages that look like trade summaries
    # We'll search for "Profit" or "P/L" or "Closed" or "Fill" or "Evaluator"
    patterns = [
        rb"Profit/Loss", rb"P/L", rb"Closed Trade", rb"Evaluator", rb"OrderStatus=Filled",
        rb"Entry:", rb"Exit:", rb"Filled"
    ]
    
    unique_contexts = set()
    
    print(f"--- Searching in {file_path} ---")
    for pattern in patterns:
        for match in re.finditer(pattern, data):
            # Capture 200 bytes around the match
            start = max(0, match.start() - 100)
            end = min(len(data), match.end() + 200)
            context = data[start:end]
            # Strip non-printable or weird binary
            clean_context = re.sub(rb'[^\x20-\x7E]', rb'.', context).decode(errors='ignore')
            unique_contexts.add(clean_context)
            
    for ctx in sorted(list(unique_contexts)):
        print(f"\nCONTEXT:\n{ctx}")

if __name__ == "__main__":
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_19550-12-05_UTC.ES-TM_3.data"
    if os.path.exists(path):
        dump_trade_related_strings(path)
    else:
        print(f"File not found: {path}")
