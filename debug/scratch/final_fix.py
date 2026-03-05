import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
import re

for line in lines:
    if 'fetch(`${API_BASE}' in line:
        # Example: await fetch(`${API_BASE}/api/system/accounts`;
        # If it doesn't end with `) we fix it.
        # But wait, some have options: fetch(`${API_BASE}...`, { ... })
        if ', {' in line:
            # Reconstruct safely
            line = re.sub(r'fetch\(\`\$\{API_BASE\}(/api/[^`\'"]+)[`\'"]?\s*,\s*\{', r'fetch(`${API_BASE}\1`, {', line)
        else:
            # Simple case
            line = re.sub(r'fetch\(\`\$\{API_BASE\}(/api/[^`\'"]+)[`\'"]?(\);)?', r'fetch(`${API_BASE}\1`);', line)
    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Final fix completed")
