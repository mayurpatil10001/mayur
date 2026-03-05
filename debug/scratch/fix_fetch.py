import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the mess by replacing '/api' with '`{API_BASE}/api`' inside backticks where fetch is called
# But simpler: replace all fetch('/api/...) with fetch(`${API_BASE}/api/...)

import re
fixed_content = re.sub(r"fetch\('/api/", "fetch(`${API_BASE}/api/", content)
fixed_content = re.sub(r"fetch\(\"/api/", "fetch(`${API_BASE}/api/", fixed_content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(fixed_content)
print("Fixed fetch calls")
