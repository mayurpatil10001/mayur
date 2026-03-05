import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# First, undo the damage by restoring a sane state if possible, or just fix the known broken patterns
import re

# Fix the broken confirm/alert with `)
content = content.replace('confirm(`)', 'confirm("')
content = content.replace('alert(`)', 'alert("')

# Fix the broken fetch closing paren
content = re.sub(r'fetch\(\`\$\{API_BASE\}(/api/[^`]+)\`([^)]*)\)\)', r'fetch(`${API_BASE}\1`\2)', content)

# Specific fix for handleRestartBackend
content = content.replace("fetch(`${API_BASE}/api/system/restart`), { method: 'POST' });", "fetch(`${API_BASE}/api/system/restart`, { method: 'POST' });")

# General fix for any other fetch calls that were messed up
content = re.sub(r"fetch\(\`\$\{API_BASE\}(/api/[^\`]+)\`\),", r"fetch(`${API_BASE}\1`,", content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Manually fixed regex damage")
