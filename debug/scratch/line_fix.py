import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
import re

for line in lines:
    if 'fetch' in line and '${API_BASE}' in line:
        # Example: await fetch(`${API_BASE}/api/system/accounts');
        # Find the path part
        match = re.search(r'\$\{API_BASE\}(/[^`\'"]+)', line)
        if match:
            path = match.group(1)
            # Reconstruct the line part
            # Look for whatever quote preceded ${API_BASE}
            # and whatever quote followed the path
            fixed_line = re.sub(r'fetch\([`\'"]\$\{API_BASE\}/[^`\'"]+[`\'"]', f"fetch(`${{API_BASE}}{path}`", line)
            fixed_lines.append(fixed_line)
        else:
            fixed_lines.append(line)
    else:
        fixed_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)
print("Line by line fix completed")
