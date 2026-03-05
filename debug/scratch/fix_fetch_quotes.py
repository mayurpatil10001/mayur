import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Fix backtick opening with single quote closing
fixed_content = re.sub(r"fetch\(\`\$\{API_BASE\}(/api/[^']+)'", r"fetch(`${API_BASE}\1`)", content)
fixed_content = re.sub(r"fetch\(\`\$\{API_BASE\}(/api/[^\"]+)\"", r"fetch(`${API_BASE}\1`)", fixed_content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)
print("Fixed mismatched quotes in fetch calls")
