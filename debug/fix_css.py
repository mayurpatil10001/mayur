import os

file_path = r"c:\SierraChart\SC results WF\frontend\src\pages\TradeImport\TradeImport.css"

with open(file_path, 'rb') as f:
    content = f.read()

# Look for the last valid brace
marker = b'font-size: 14px;\r\n}'
if marker not in content:
    marker = b'font-size: 14px;\n}'

split_content = content.split(marker)
clean_base = split_content[0] + marker

animation = b"""
@keyframes loading-pulse {
  0% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.1); }
  100% { opacity: 0.4; transform: scale(0.8); }
}
"""

with open(file_path, 'wb') as f:
    f.write(clean_base)
    f.write(animation)

print("Fixed CSS file.")
