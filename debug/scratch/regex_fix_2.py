import os
import re

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix fetch calls with mismatched quotes
# Example: fetch(`${API_BASE}/api/system/accounts'
# Should be: fetch(`${API_BASE}/api/system/accounts`)

def fix_fetch(match):
    full_call = match.group(0)
    # Extract the quote type and the path
    # fetch(`${API_BASE}/...`)
    m = re.search(r'fetch\(([`\'"])\$\{API_BASE\}(/[^`\'"]+)([`\'"])', full_call)
    if m:
        # If they match and they are backticks, it's fine
        if m.group(1) == '`' and m.group(3) == '`':
            return full_call
        # Otherwise, force backticks
        return f"fetch(`${{API_BASE}}{m.group(2)}`"
    
    # Handle cases where it might be fetch(`${API_BASE}/...`, { ... })
    m = re.search(r'fetch\(([`\'"])\$\{API_BASE\}(/[^`\'"]+)([`\'"])\s*,', full_call)
    if m:
        return f"fetch(`${{API_BASE}}{m.group(2)}`,"
    
    return full_call

# Broad replacement for fetch calls
content = re.sub(r"fetch\(([`\'"])\$\{API_BASE\}(/[^`\'"]+)([`\'"])", r"fetch(`${API_BASE}\2`)", content)
# For the comma case
content = re.sub(r"fetch\(([`\'"])\$\{API_BASE\}(/[^`\'"]+)([`\'"])\s*,", r"fetch(`${API_BASE}\2`,", content)

# Check for any remaining garbage in line 873 area that Select-String showed
# 873: fetchData();pi/system/import-start`, {
# Wait, let me check line 873 again.

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Regex fixed fetch calls")
