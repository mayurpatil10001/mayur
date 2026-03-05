import os
import re

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    # Check for matched quotes/backticks on the same line if they are simple calls
    # This is a very rough check
    line_num = i + 1
    
    # Count occurrences of each quote type
    single = line.count("'")
    double = line.count('"')
    backtick = line.count("`")
    
    if (single % 2 != 0 or double % 2 != 0 or backtick % 2 != 0):
        # Might be a mismatch, but might span multiple lines
        # Let's filter for common cases like alert/confirm/fetch
        if any(kw in line for kw in ['alert(', 'confirm(', 'fetch(', '`status-dot']):
            # If it's a single line call, it should have even counts
            # Exceptions exist for escapes or nested but we don't use much of that here
             print(f"Potential mismatch at line {line_num}: {line.strip()}")

print("Check complete")
