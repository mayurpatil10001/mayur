import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Fix the specific broken alert line 330
# alert(data.message || `)VIX Data Imported");
content = content.replace('alert(data.message || `)VIX Data Imported");', 'alert(data.message || "VIX Data Imported");')

# Fix any other similar patterns like `)
content = content.replace('`)', '"')
# And confirm(`) if any left
content = content.replace('confirm(`)', 'confirm("')
# And alert(`) if any left
content = content.replace('alert(`)', 'alert("')

# Actually, let's look for fetch calls that might still be broken
# My previous attempt at fixing quotes might have been too specific or too broad
# Let's just fix the mismatched quotes around ${API_BASE}

# Pattern: fetch(`${API_BASE}/something') -> fetch(`${API_BASE}/something`)
content = re.sub(r"fetch\(\`\$\{API_BASE\}(/api/[^']+)'", r"fetch(`${API_BASE}\1`)", content)
content = re.sub(r"fetch\(\`\$\{API_BASE\}(/api/[^\"]+)\"", r"fetch(`${API_BASE}\1`)", content)

# Check for the literal `)VIX Data Imported"
content = content.replace('`)VIX Data Imported"', '"VIX Data Imported"')
content = content.replace('`)Restart triggered. Please wait 5-10 seconds."', '"Restart triggered. Please wait 5-10 seconds."')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Manually fixed known broken patterns")
