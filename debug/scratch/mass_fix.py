import os

file_path = r'c:\SierraChart\SC results WF\frontend\src\pages\Monitoring\Monitoring.tsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all occurrences of `) with just ' or " as appropriate
# In line 328 it was method: `)POST'
# So replacing `) with ' would make it method: 'POST'
# But wait, it might be `)POST` if it was meant to be template literal.
# Most likely it was 'POST' and got mangled.

content = content.replace('`)', "'")

# Also check for other mangled quotes
content = content.replace("`{API_BASE}", "`${API_BASE}")
content = content.replace("${API_BASE}'", "${API_BASE}`")
content = content.replace("${API_BASE}\"", "${API_BASE}`")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Massively replaced mangled backticks")
